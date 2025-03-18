from django.urls import path
from .views import (
    CreateCompanyView, CreateJobView, GetJobView, ListJobsView,
    ApplyForJobView, ListApplicationsView, UpdateApplicationStatusView,
    GetMatchingCandidatesView
)

urlpatterns = [
    path('companies/', CreateCompanyView.as_view(), name='create_company'),
    path('jobs/', CreateJobView.as_view(), name='create_job'),
    path('jobs/<uuid:job_id>/', GetJobView.as_view(), name='get_job'),
    path('jobs/list/', ListJobsView.as_view(), name='list_jobs'),
    path('jobs/<uuid:job_id>/apply/', ApplyForJobView.as_view(), name='apply_for_job'),
    path('applications/', ListApplicationsView.as_view(), name='list_applications'),
    path('applications/<uuid:application_id>/status/', UpdateApplicationStatusView.as_view(), name='update_application_status'),
    path('jobs/<uuid:job_id>/matches/', GetMatchingCandidatesView.as_view(), name='get_matching_candidates'),
]