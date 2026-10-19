# -*- coding: utf-8 -*-
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
