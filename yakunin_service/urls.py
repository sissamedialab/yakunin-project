from django.urls import path

from . import views

urlpatterns = [
    path("test/", views.test_service, name="test"),
    path("mkpdf/", views.mkpdf, name="mkpdf"),
    path("mkpdf/ws/", views.mkpdf, name="mkpdf_ws"),
    path("watermark/", views.watermark, name="watermark"),
    path("watermark/ws/", views.watermark, name="watermark_ws"),
]
