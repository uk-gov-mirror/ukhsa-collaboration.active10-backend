from schemas.activity import UserActivityRequestSchema
from service.aws_sns_service import send_message_to_sns_topic
from service.aws_sqs_service import send_message_to_sqs_queue
from utils.base_config import config as settings

async def load_activities_data_in_sns(activity: UserActivityRequestSchema, user_id) -> None:
    activity_payload = activity.model_dump()
    activity_payload["user_id"] = str(user_id)
    target_sns_topic_arn = settings.aws_sns_activity_topic_arn

    send_message_to_sns_topic(topic=target_sns_topic_arn, record=activity_payload)
