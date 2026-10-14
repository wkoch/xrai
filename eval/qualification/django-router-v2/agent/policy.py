"""Two existing deployment policies; immutable during this configuration task."""
class DefaultPolicy:
    def allow_migrate(self, db, app_label, **hints):
        return db == "default"


class LedgerPolicy:
    def allow_migrate(self, db, app_label, **hints):
        if app_label == "ledger":
            return db == "reporting"
        return None
