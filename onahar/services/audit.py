from onahar.models import OnaharAuditLog


def write_audit(
    *,
    action: str,
    actor=None,
    previous_value=None,
    new_value=None,
    metadata=None,
) -> OnaharAuditLog:
    return OnaharAuditLog.objects.create(
        action=action,
        actor=actor,
        previous_value=previous_value,
        new_value=new_value,
        metadata=metadata or {},
    )
