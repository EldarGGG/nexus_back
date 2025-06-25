from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/matrix/(?P<room_name>\w+)/$', consumers.MatrixConsumer.as_asgi()),
    re_path(r'ws/company/(?P<company_id>[\w-]+)/$', consumers.CompanyConsumer.as_asgi()),
    re_path(r'ws/bridge/(?P<bridge_id>[\w-]+)/$', consumers.BridgeConsumer.as_asgi()),
]
