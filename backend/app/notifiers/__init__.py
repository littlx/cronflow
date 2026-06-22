from app.notifiers.base import NOTIFIERS, Notifier, notify_event
from app.notifiers.webhook_notifier import webhook_notifier

# 渠道注册: 新增 sms/email/dingtalk 时, 在此追加一行即可
NOTIFIERS[webhook_notifier.name] = webhook_notifier

__all__ = ["Notifier", "NOTIFIERS", "notify_event"]
