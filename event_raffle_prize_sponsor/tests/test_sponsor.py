# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import base64
import io
from datetime import timedelta
from unittest.mock import patch

from lxml import etree
from PIL import Image

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import new_test_user, tagged
from odoo.tests.common import TransactionCase
from odoo.tools.safe_eval import safe_eval

from odoo.addons.mail.models.mail_template import MailTemplate

from .common import SponsorDataMixin


@tagged("post_install", "-at_install")
class TestSponsor(SponsorDataMixin, TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._sponsor_setup()

    # Who may submit prizes

    def test_sponsor_events_follow_the_registration_and_the_event(self):
        Event = self.env["event.event"]
        alice = self.alice.partner_id
        self.assertEqual(Event._raffle_sponsor_events(alice), self.open_event)
        # Another contact of the same company, without a registration.
        self.assertEqual(
            Event._raffle_sponsor_events(self.bob.partner_id), self.open_event
        )
        self.assertFalse(Event._raffle_sponsor_events(self.visitor.partner_id))
        self._sponsor_registration(self.bob, self.second_event)
        self.assertEqual(
            Event._raffle_sponsor_events(alice),
            self.open_event | self.second_event,
        )
        self.second_event.raffle_sponsor_managed = False
        self.assertEqual(Event._raffle_sponsor_events(alice), self.open_event)
        self.alice_registration.action_cancel()
        self.assertFalse(Event._raffle_sponsor_events(alice))
        self.alice_registration.action_confirm()
        self.alice_registration.is_raffle_sponsor = False
        self.assertFalse(Event._raffle_sponsor_events(alice))
        self.alice_registration.is_raffle_sponsor = True
        now = fields.Datetime.now()
        self.open_event.write(
            {"date_begin": now - timedelta(days=1), "date_end": now}
        )
        self.assertFalse(Event._raffle_sponsor_events(alice))

    # Sponsor contact and invitation

    def test_sponsor_contact_is_the_attendee_not_the_booker(self):
        self.assertEqual(
            self.alice_registration.raffle_sponsor_partner_id,
            self.alice.partner_id,
        )
        booker = self.env["res.partner"].create(
            {"name": "Bea Booker", "email": "bea.booker@example.com"}
        )
        attendee = self.env["res.partner"].create(
            {"name": "Ada Attendee", "email": "Ada.Attendee@example.com"}
        )
        booked = self.env["event.registration"].create(
            {
                "event_id": self.open_event.id,
                "partner_id": booker.id,
                "name": "Ada Attendee",
                "email": "ada.attendee@example.com",
                "is_raffle_sponsor": True,
            }
        )
        # The attendee's contact is found when the invitation is sent.
        self.assertFalse(booked.raffle_sponsor_partner_id)
        self.assertEqual(booked._raffle_sponsor_contact(), attendee)
        self.assertEqual(booked.raffle_sponsor_partner_id, attendee)
        unknown = self.env["event.registration"].create(
            {
                "event_id": self.open_event.id,
                "partner_id": booker.id,
                "name": "Nell Newcomer",
                "email": "nell.newcomer@example.com",
                "is_raffle_sponsor": True,
            }
        )
        self.assertFalse(unknown.raffle_sponsor_partner_id)
        self.assertEqual(unknown.raffle_sponsor_account_state, "none")
        contact = unknown._raffle_sponsor_contact()
        self.assertEqual(contact.email, "nell.newcomer@example.com")
        self.assertEqual(contact.name, "Nell Newcomer")
        self.assertNotEqual(contact, booker)
        self.assertEqual(unknown.raffle_sponsor_partner_id, contact)
        nomail = self.env["event.registration"].create(
            {
                "event_id": self.open_event.id,
                "name": "Otto Nomail",
                "is_raffle_sponsor": True,
            }
        )
        with self.assertRaisesRegex(UserError, "no valid email"):
            nomail.action_raffle_sponsor_invite()

    def test_an_email_match_never_binds_a_contact_with_an_account(self):
        """A portal user who puts a sponsor's email on their own contact
        gets no access to the sponsor's prizes."""
        Event = self.env["event.event"]
        email = "rowan.realsponsor@example.com"
        intruder = self._portal_user(
            "intruder_ivo", "Ivo Intruder", company=False
        )
        intruder.partner_id.email = email
        # A website registration of a visitor who is not signed in has no
        # contact.
        registration = self.env["event.registration"].create(
            {
                "event_id": self.open_event.id,
                "name": "Rowan Realsponsor",
                "email": email,
                "is_raffle_sponsor": True,
            }
        )
        self.assertFalse(registration.raffle_sponsor_partner_id)
        self.assertEqual(registration.raffle_sponsor_account_state, "none")
        self.assertFalse(Event._raffle_sponsor_events(intruder.partner_id))
        with self.assertRaisesRegex(UserError, "An account already uses"):
            registration.with_user(
                self.organizer
            ).action_raffle_sponsor_invite()
        self.assertFalse(registration.raffle_sponsor_partner_id)
        self.assertFalse(Event._raffle_sponsor_events(intruder.partner_id))
        # The organization sets the contact explicitly.
        registration.partner_id = intruder.partner_id
        self.assertEqual(
            registration.raffle_sponsor_partner_id, intruder.partner_id
        )
        registration.partner_id = False
        self.assertFalse(registration.raffle_sponsor_partner_id)
        # A later change of an email moves no stored sponsor contact: the
        # invited contact stays, and the booker who takes the attendee's
        # email gets nothing.
        booker = self.env["res.partner"].create(
            {"name": "Bo Booker", "email": "bo.booker@example.com"}
        )
        booked = self.env["event.registration"].create(
            {
                "event_id": self.open_event.id,
                "partner_id": booker.id,
                "name": "Una Attendee",
                "email": "una.attendee@example.com",
                "is_raffle_sponsor": True,
            }
        )
        booked.with_user(self.organizer).action_raffle_sponsor_invite()
        invited = booked.raffle_sponsor_partner_id
        self.assertEqual(invited.email, "una.attendee@example.com")
        self.assertTrue(invited.user_ids)
        booker.email = "una.attendee@example.com"
        booked.email = "bo.booker@example.com"
        self.assertEqual(booked.raffle_sponsor_partner_id, invited)
        self.alice.partner_id.email = "alice.elsewhere@example.com"
        self.alice_registration.email = email
        self.assertEqual(
            self.alice_registration.raffle_sponsor_partner_id,
            self.alice.partner_id,
        )

    def test_invitation_grants_portal_access_and_sends_the_template(self):
        registration = self.env["event.registration"].create(
            {
                "event_id": self.open_event.id,
                "name": "Ivy Invited",
                "email": "ivy.invited@example.com",
                "is_raffle_sponsor": True,
            }
        )
        self.assertEqual(registration.raffle_sponsor_account_state, "none")
        template = self.env.ref("portal.mail_template_data_portal_welcome")
        sent = []
        original = MailTemplate.send_mail

        def spy(record, res_id, *args, **kwargs):
            sent.append((record.id, res_id))
            return original(record, res_id, *args, **kwargs)

        organizer = registration.with_user(self.organizer)
        with patch.object(MailTemplate, "send_mail", spy):
            organizer.action_raffle_sponsor_invite()
        partner = registration.raffle_sponsor_partner_id
        user = partner.user_ids
        self.assertEqual(len(user), 1)
        self.assertTrue(user._is_portal())
        self.assertEqual(user.login, "ivy.invited@example.com")
        self.assertEqual([tid for tid, __ in sent], [template.id])
        registration.invalidate_recordset(["raffle_sponsor_account_state"])
        self.assertEqual(registration.raffle_sponsor_account_state, "invited")
        # Not accepted yet: the invitation is sent again.
        with patch.object(MailTemplate, "send_mail", spy):
            organizer.action_raffle_sponsor_invite()
        self.assertEqual(len(sent), 2)
        self.assertEqual(partner.user_ids, user)
        user.with_user(user)._update_last_login()
        user.invalidate_recordset(["log_ids", "login_date"])
        registration.invalidate_recordset(["raffle_sponsor_account_state"])
        self.assertEqual(registration.raffle_sponsor_account_state, "active")
        # An internal user who never signed in needs no invitation: no
        # banner and no button.
        internal = self._sponsor_registration(self.organizer, self.open_event)
        self.assertFalse(self.organizer.login_date)
        self.assertEqual(internal.raffle_sponsor_account_state, "active")
        self.assertEqual(self._shown_banners(internal), {})
        with self.assertRaisesRegex(UserError, "internal user"):
            internal.action_raffle_sponsor_invite()
        # A user outside the event group sends nothing.
        employee = new_test_user(
            self.env, login="sponsor_employee", groups="base.group_user"
        )
        with self.assertRaises(AccessError):
            registration.with_user(employee).action_raffle_sponsor_invite()

    def test_registration_desk_sends_no_invitation(self):
        """The invitation creates a portal account: the registration desk,
        which writes registrations, does not send it."""
        desk = new_test_user(
            self.env,
            login="sponsor_desk",
            groups="base.group_user,event.group_event_registration_desk",
            name="Desk Clerk",
        )
        registration = self.env["event.registration"].create(
            {
                "event_id": self.open_event.id,
                "name": "Dee Desk",
                "email": "dee.desk@example.com",
                "is_raffle_sponsor": True,
            }
        )
        registration.with_user(desk).check_access("write")
        with self.assertRaises(AccessError):
            registration.with_user(desk).action_raffle_sponsor_invite()
        self.assertFalse(
            self.env["res.users"].search(
                [("login", "=", "dee.desk@example.com")]
            )
        )

    def _shown_banners(self, registration):
        """{banner class: names of its buttons} of the sponsor banners that
        the registration form shows for `registration`, from the invisible
        expressions of the form as the web client evaluates them."""
        views = self.env["event.registration"].get_views([(False, "form")])
        tree = etree.fromstring(views["views"]["form"]["arch"])
        values = {
            name: registration[name]
            for name in (
                "is_raffle_sponsor",
                "raffle_sponsor_managed",
                "raffle_sponsor_account_state",
            )
        }
        shown = {}
        banners = tree.xpath(
            "//div[contains(@class, 'o_raffle_sponsor_no_account') or "
            "contains(@class, 'o_raffle_sponsor_invited')]"
        )
        self.assertEqual(len(banners), 2)
        for banner in banners:
            if safe_eval(banner.get("invisible") or "False", values):
                continue
            name = next(
                c for c in banner.get("class").split() if c[:2] == "o_"
            )
            shown[name] = {b.get("name") for b in banner.xpath(".//button")}
        return shown

    def test_registration_form_shows_the_banner_of_the_account(self):
        invite = "action_raffle_sponsor_invite"
        template = "action_open_raffle_sponsor_invitation_template"
        registration = self.env["event.registration"].create(
            {
                "event_id": self.open_event.id,
                "name": "Ben Banner",
                "email": "ben.banner@example.com",
                "is_raffle_sponsor": True,
            }
        )
        self.assertEqual(
            self._shown_banners(registration),
            {"o_raffle_sponsor_no_account": {invite, template}},
        )
        registration.with_user(self.organizer).action_raffle_sponsor_invite()
        registration.invalidate_recordset(["raffle_sponsor_account_state"])
        self.assertEqual(registration.raffle_sponsor_account_state, "invited")
        self.assertEqual(
            self._shown_banners(registration),
            {"o_raffle_sponsor_invited": {invite, template}},
        )
        user = registration.raffle_sponsor_partner_id.user_ids
        user.with_user(user)._update_last_login()
        user.invalidate_recordset(["log_ids", "login_date"])
        registration.invalidate_recordset(["raffle_sponsor_account_state"])
        self.assertEqual(registration.raffle_sponsor_account_state, "active")
        self.assertEqual(self._shown_banners(registration), {})
        # Neither banner outside a sponsor registration of a
        # sponsor-managed event.
        other = self.env["event.registration"].create(
            {
                "event_id": self.open_event.id,
                "name": "Nora Nosponsor",
                "email": "nora.nosponsor@example.com",
            }
        )
        self.assertEqual(other.raffle_sponsor_account_state, "none")
        self.assertEqual(self._shown_banners(other), {})
        unmanaged = self.env["event.registration"].create(
            {
                "event_id": self.second_event.id,
                "name": "Una Unmanaged",
                "email": "una.unmanaged@example.com",
                "is_raffle_sponsor": True,
            }
        )
        self.second_event.raffle_sponsor_managed = False
        self.assertEqual(unmanaged.raffle_sponsor_account_state, "none")
        self.assertEqual(self._shown_banners(unmanaged), {})

    def test_registration_form_warns_and_links_the_template_for_editors(self):
        editor_group = self.env.ref("mail.group_mail_template_editor")
        self.env.ref("base.group_user").implied_ids -= editor_group
        restricted = new_test_user(
            self.env,
            login="sponsor_no_template",
            groups="base.group_user,event.group_event_user",
        )
        self.assertFalse(
            restricted.has_group("mail.group_mail_template_editor")
        )
        editor = new_test_user(
            self.env,
            login="sponsor_template_editor",
            groups="base.group_user,event.group_event_user,"
            "mail.group_mail_template_editor",
        )

        def arch(user):
            views = (
                self.env["event.registration"]
                .with_user(user)
                .get_views([(False, "form")])
            )
            return etree.fromstring(views["views"]["form"]["arch"])

        method = "action_open_raffle_sponsor_invitation_template"
        for user, shown in ((editor, True), (restricted, False)):
            with self.subTest(user=user.login):
                tree = arch(user)
                self.assertEqual(
                    bool(tree.xpath(f"//button[@name='{method}']")), shown
                )
                self.assertTrue(
                    tree.xpath(
                        "//button[@name='action_raffle_sponsor_invite']"
                    )
                )
        action = getattr(self.alice_registration.with_user(editor), method)()
        self.assertEqual(action["res_model"], "mail.template")
        self.assertEqual(
            action["res_id"],
            self.env.ref("portal.mail_template_data_portal_welcome").id,
        )
        with self.assertRaises(AccessError):
            getattr(self.alice_registration.with_user(restricted), method)()

    # Portal prizes and their approval

    def test_portal_prize_is_submitted_and_offered_nowhere(self):
        template = self._submit()
        self.assertEqual(template.raffle_sponsor_state, "submitted")
        self.assertFalse(template.active)
        self.assertFalse(template.is_published)
        self.assertFalse(template.raffle_member_sale_ok)
        self.assertTrue(template.is_raffle_prize)
        self.assertTrue(template.is_storable)
        self.assertEqual(template.raffle_sponsor_id, self.sponsor)
        self.assertEqual(template.raffle_event_ids, self.open_event)
        self.assertEqual(template.raffle_band_id, self.band_a)
        product = template.with_context(active_test=False).product_variant_ids
        self.assertFalse(product.active)
        self.env["stock.quant"]._update_available_quantity(
            product, self.warehouse.lot_stock_id, 2
        )
        draw = self._fair_draw("Win Ner")
        self.assertNotIn(product, draw._prize_allowed_products())
        self.assertTrue(draw._prize_refusal(product))
        wizard = (
            self.env["event.raffle.prize.choose.wizard"]
            .with_context(default_draw_id=draw.id)
            .create({})
        )
        self.assertNotIn(product, wizard.allowed_product_ids)
        with self.assertRaises(UserError):
            draw._prize_claim(product)
        # Restoring it by hand is refused: approval restores it.
        with self.assertRaises(ValidationError):
            template.active = True
        template.raffle_band_id = False
        with self.assertRaisesRegex(UserError, "token category"):
            template.with_user(self.manager).action_raffle_sponsor_approve()
        template.raffle_band_id = self.band_a
        with self.assertRaises(AccessError):
            template.with_user(self.organizer).action_raffle_sponsor_approve()
        template.with_user(self.manager).action_raffle_sponsor_approve()
        self.assertEqual(template.raffle_sponsor_state, "approved")
        self.assertTrue(template.active)
        self.assertTrue(product.active)
        self.assertTrue(template.is_published)
        self.assertIn(product, draw._prize_allowed_products())
        draw._prize_claim(product)
        self.assertEqual(draw.claim_state, "reserved")

    def test_staff_prizes_are_approved_and_notify_nobody(self):
        self.assertEqual(self.mug.raffle_sponsor_state, "approved")
        self.assertTrue(self.mug.active)
        self.assertFalse(self._notifications(self.mug.product_tmpl_id))

    def test_refusal_reason_then_the_sponsor_edit_submits_again(self):
        template = self._submit()
        wizard = (
            self.env["event.raffle.prize.refuse.wizard"]
            .with_user(self.manager)
            .create({"product_tmpl_id": template.id, "reason": "   "})
        )
        with self.assertRaises(UserError):
            wizard.action_refuse()
        action = template.with_user(
            self.manager
        ).action_open_raffle_sponsor_refuse_wizard()
        wizard = (
            self.env[action["res_model"]]
            .with_user(self.manager)
            .with_context(action["context"])
            .create({"reason": "Add a photo of the lamp."})
        )
        wizard.action_refuse()
        self.assertEqual(template.raffle_sponsor_state, "refused")
        self.assertEqual(
            template.raffle_sponsor_refusal_reason, "Add a photo of the lamp."
        )
        self.assertFalse(template.active)
        with self.assertRaises(UserError):
            template._raffle_sponsor_refuse("Twice")
        before = self._notifications(template)
        template._raffle_sponsor_portal_write(
            self.open_event, self._portal_values(name="Sponsor Lamp XL")
        )
        self.assertEqual(template.raffle_sponsor_state, "submitted")
        self.assertFalse(template.raffle_sponsor_refusal_reason)
        self.assertEqual(template.name, "Sponsor Lamp XL")
        again = self._notifications(template) - before
        self.assertEqual(len(again), 1)
        self.assertIn("review it again", str(again.body))
        # An edit of a submitted prize tells the managers it changed.
        template._raffle_sponsor_portal_write(
            self.open_event, self._portal_values(name="Sponsor Lamp XXL")
        )
        changed = self._notifications(template) - before - again
        self.assertEqual(len(changed), 1)
        self.assertIn("changed the prize", str(changed.body))
        template.with_user(self.manager).action_raffle_sponsor_approve()
        with self.assertRaises(UserError):
            template._raffle_sponsor_portal_write(
                self.open_event, self._portal_values()
            )
        with self.assertRaises(UserError):
            template._raffle_sponsor_portal_withdraw()

    def test_sponsor_edit_keeps_the_category_the_reviewer_chose(self):
        template = self._submit()
        self.assertEqual(template.raffle_band_id, self.band_a)
        template.raffle_band_id = self.band_b
        before = self._notifications(template)
        # Saving the form unchanged writes nothing and notifies nobody.
        template._raffle_sponsor_portal_write(
            self.open_event, self._portal_values()
        )
        self.assertEqual(template.raffle_band_id, self.band_b)
        self.assertFalse(self._notifications(template) - before)
        # A new value keeps the category, and the managers hear of it.
        template._raffle_sponsor_portal_write(
            self.open_event, self._portal_values(list_price=35.0)
        )
        self.assertEqual(template.list_price, 35.0)
        self.assertEqual(template.raffle_band_id, self.band_b)
        changed = self._notifications(template) - before
        self.assertEqual(len(changed), 1)
        self.assertEqual(changed.partner_ids, self.manager.partner_id)
        self.assertIn("Sponsor Example changed the prize", str(changed.body))
        self.assertIn("Sponsor Lamp", changed.subject)
        # A category that follows the price keeps following it.
        other = self._submit(name="Sponsor Mug")
        other._raffle_sponsor_portal_write(
            self.open_event, self._portal_values("Sponsor Mug", list_price=75)
        )
        self.assertEqual(other.raffle_band_id, self.band_b)

    def test_submission_notifies_the_managers_else_the_responsible(self):
        template = self._submit()
        message = self._notifications(template)
        self.assertEqual(len(message), 1)
        self.assertEqual(message.partner_ids, self.manager.partner_id)
        self.assertIn("Sponsor Example submitted the prize", str(message.body))
        self.assertIn("Open Fair", str(message.body))
        self.assertIn("Sponsor Lamp", message.subject)
        self.assertTrue(
            message.notification_ids.filtered(
                lambda n: n.res_partner_id == self.manager.partner_id
            )
        )
        self.open_event.raffle_sponsor_manager_ids = False
        fallback = self._notifications(self._submit(name="Sponsor Mug"))
        self.assertEqual(fallback.partner_ids, self.responsible.partner_id)
        self.open_event.user_id = False
        self.assertFalse(self._notifications(self._submit(name="Sponsor Cap")))

    def test_withdraw_deletes_a_prize_unused_by_the_organization(self):
        template = self._submit()
        template._raffle_sponsor_portal_withdraw()
        self.assertFalse(template.exists())
        used = self._submit(name="Sponsor Kept")
        product = used.with_context(active_test=False).product_variant_ids
        self.env["stock.quant"]._update_available_quantity(
            product, self.warehouse.lot_stock_id, 1
        )
        self.env["stock.move"].create(
            {
                "name": "Received",
                "product_id": product.id,
                "product_uom": product.uom_id.id,
                "product_uom_qty": 1,
                "location_id": self.warehouse.lot_stock_id.id,
                "location_dest_id": self.warehouse.lot_stock_id.id,
            }
        )
        with self.assertRaisesRegex(UserError, "ask the organization"):
            used._raffle_sponsor_portal_withdraw()
        self.assertTrue(used.exists())

    def test_portal_values_keep_the_portal_fields_only(self):
        values = self._portal_values(
            raffle_band_id=self.band_b.id,
            raffle_sponsor_state="approved",
            raffle_sponsor_id=self.rival.id,
            sale_ok=False,
            is_published=True,
            active=True,
            raffle_member_sale_ok=True,
            raffle_closing_prize=True,
        )
        template = self.env["product.template"]._raffle_sponsor_portal_create(
            self.alice.partner_id, self.open_event, values
        )
        self.assertEqual(template.raffle_sponsor_state, "submitted")
        self.assertEqual(template.raffle_band_id, self.band_a)
        self.assertEqual(template.raffle_sponsor_id, self.sponsor)
        self.assertTrue(template.sale_ok)
        self.assertFalse(template.is_published)
        self.assertFalse(template.active)
        self.assertFalse(template.raffle_member_sale_ok)
        self.assertFalse(template.raffle_closing_prize)

    def test_sponsor_without_company_is_the_person(self):
        self._sponsor_registration(self.visitor, self.open_event)
        template = self._submit(user=self.visitor)
        self.assertEqual(template.raffle_sponsor_id, self.visitor.partner_id)

    # Photo

    def test_photo_is_resized_and_non_images_are_refused(self):
        Template = self.env["product.template"]
        buffer = io.BytesIO()
        Image.new("RGB", (2500, 1000), (10, 120, 200)).save(buffer, "JPEG")
        stored = Template._raffle_sponsor_photo(buffer.getvalue())
        image = Image.open(io.BytesIO(base64.b64decode(stored)))
        self.assertEqual(image.size, (1920, 768))
        svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script/></svg>'
        for data in (b"plain text", svg, b"\x89PNG\r\n\x1a\nbroken"):
            with self.subTest(data=data[:12]), self.assertRaises(UserError):
                Template._raffle_sponsor_photo(data)

    def test_photo_is_encoded_again_without_its_metadata(self):
        """A small photo keeps no EXIF data (an invented camera and GPS
        position) and is turned by its orientation; a large WebP photo is
        reduced like any other."""
        Template = self.env["product.template"]
        exif = Image.Exif()
        exif[0x0110] = "InventedCam"
        exif[0x0112] = 6
        exif.get_ifd(0x8825).update({1: "N", 2: (45.0, 30.0, 0.0)})
        buffer = io.BytesIO()
        Image.new("RGB", (800, 600), (10, 120, 200)).save(
            buffer, "JPEG", exif=exif
        )
        source = buffer.getvalue()
        self.assertTrue(Image.open(io.BytesIO(source)).getexif())
        stored = base64.b64decode(Template._raffle_sponsor_photo(source))
        self.assertNotEqual(stored, source)
        self.assertNotIn(b"InventedCam", stored)
        image = Image.open(io.BytesIO(stored))
        self.assertEqual(image.format, "JPEG")
        self.assertEqual(image.size, (600, 800))
        self.assertFalse(image.getexif())
        self.assertNotIn("exif", image.info)
        buffer = io.BytesIO()
        Image.new("RGB", (3000, 2000), (10, 120, 200)).save(
            buffer, "WEBP", exif=exif
        )
        stored = base64.b64decode(
            Template._raffle_sponsor_photo(buffer.getvalue())
        )
        self.assertNotIn(b"InventedCam", stored)
        image = Image.open(io.BytesIO(stored))
        self.assertEqual(image.format, "JPEG")
        self.assertEqual(image.size, (1280, 1920))
        self.assertFalse(image.getexif())
        # Transparency is kept, as a PNG.
        buffer = io.BytesIO()
        Image.new("RGBA", (40, 20), (10, 120, 200, 0)).save(buffer, "PNG")
        image = Image.open(
            io.BytesIO(
                base64.b64decode(
                    Template._raffle_sponsor_photo(buffer.getvalue())
                )
            )
        )
        self.assertEqual((image.format, image.mode), ("PNG", "RGBA"))

    # Translations

    def test_labels_in_french(self):
        self.env["res.lang"]._activate_lang("fr_CA")
        self.env["ir.module.module"]._load_module_terms(
            ["event_raffle_prize_sponsor"], ["fr_CA"], overwrite=True
        )
        fr = self.env(context=dict(self.env.context, lang="fr_CA"))
        registration = fr["event.registration"].fields_get(
            ["is_raffle_sponsor"]
        )
        self.assertEqual(
            registration["is_raffle_sponsor"]["string"], "Est commanditaire"
        )
        event = fr["event.event"].fields_get(
            ["raffle_sponsor_managed", "raffle_sponsor_manager_ids"]
        )
        self.assertEqual(
            event["raffle_sponsor_managed"]["string"],
            "Gérer avec commanditaires",
        )
        self.assertEqual(
            event["raffle_sponsor_manager_ids"]["string"],
            "Responsables des commandites",
        )
        states = dict(
            fr["product.template"].fields_get(["raffle_sponsor_state"])[
                "raffle_sponsor_state"
            ]["selection"]
        )
        self.assertEqual(states["submitted"], "Soumis")
        # The product model keeps the name Odoo and the neighbour modules
        # give it.
        self.assertEqual(
            fr["ir.model"]._get("product.template").name, "Produit"
        )
        arch = fr["event.registration"].get_views([(False, "form")])
        text = arch["views"]["form"]["arch"]
        self.assertIn("Envoyer invitation", text)
        self.assertIn("Ce commanditaire n'a pas de compte", text)
