# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux  (Martial@Bigras.ca)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
# Odoo découvre les tests d'un module via les imports de ce fichier
# (pas seulement la présence de fichiers dans tests/) - les deux
# fichiers ci-dessous sont donc exécutés automatiquement avec
# `--test-enable --test-tags rlq_survey_report`.
#
# test_report_builder : aucune dépendance à Odoo (fonctions pures) -
#   peut aussi s'exécuter seul, sans Odoo du tout (voir son docstring).
# test_wizard : nécessite une vraie instance Odoo (TransactionCase) -
#   son import échoue proprement (plutôt que de faire échouer TOUT
#   tests/__init__.py, ce qui empêcherait même test_report_builder de
#   s'exécuter seul) si le paquet odoo n'est pas disponible - c'est
#   exactement le cas de cet environnement de développement.
from . import test_report_builder

try:
    from . import test_wizard
except ImportError:
    pass

try:
    from . import test_groupes
except ImportError:
    pass

from . import test_email_check

try:
    from . import test_registration_email
except ImportError:
    pass

from . import test_followup_report

try:
    from . import test_survey_followup
except ImportError:
    pass
