"""Verified-admin ops dashboard API views."""

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from user_management.api.permissions import IsVerifiedAdmin
from user_management.services.admin_dashboard import build_dashboard_summary


class AdminDashboardSummaryView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=['Admin Dashboard'],
        summary='Ops dashboard summary KPIs',
        responses={200: dict},
    )
    def get(self, request):
        return Response(build_dashboard_summary())
