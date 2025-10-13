from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/echo/$", consumers.EchoConsumer.as_asgi()),
    re_path(r"ws/feedback/(?P<feedback_wsname>[a-zA-Z0-9._%-]+)/$", consumers.FeedbackConsumer.as_asgi()),
]
