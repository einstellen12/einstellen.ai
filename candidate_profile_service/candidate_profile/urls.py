from django.urls import path
from .views import (
    CreateCandidateProfileView,
    GetCandidateProfileView,
    UpdateCandidateProfileView,
    UploadCVView,
    AddEducationView,
    AddWorkExperienceView,
    AddSkillView,
    AddCertificationView,
    EditPersonalInfoView,
    EditEducationView,
    EditWorkExperienceView,
    EditSkillView,
    EditCertificationView,
    JobListView,
    ApplyJobView,
    WithdrawApplicationView,
    InterviewInstructionsView,
    StartInterviewView,
    DashboardView,
    NotificationListView,
    MarkNotificationReadView
)

urlpatterns = [
    # Core Profile Operations
    path('candidates/', CreateCandidateProfileView.as_view(), name='create_candidate'),
    path('candidates/<uuid:candidate_id>/', GetCandidateProfileView.as_view(), name='get_candidate'),
    path('candidates/<uuid:candidate_id>/update/', UpdateCandidateProfileView.as_view(), name='update_candidate'),
    path('candidates/<uuid:candidate_id>/upload-cv/', UploadCVView.as_view(), name='upload_cv'),

    # Add Related Data
    path('candidates/<uuid:candidate_id>/education/', AddEducationView.as_view(), name='add_education'),
    path('candidates/<uuid:candidate_id>/work-experience/', AddWorkExperienceView.as_view(), name='add_work_experience'),
    path('candidates/<uuid:candidate_id>/skills/', AddSkillView.as_view(), name='add_skill'),
    path('candidates/<uuid:candidate_id>/certifications/', AddCertificationView.as_view(), name='add_certification'),

    # Edit Parsed Data
    path('candidates/<uuid:candidate_id>/edit-personal/', EditPersonalInfoView.as_view(), name='edit_personal_info'),
    path('education/<uuid:education_id>/edit/', EditEducationView.as_view(), name='edit_education'),
    path('work-experience/<uuid:work_experience_id>/edit/', EditWorkExperienceView.as_view(), name='edit_work_experience'),
    path('skills/<uuid:skill_id>/edit/', EditSkillView.as_view(), name='edit_skill'),
    path('certifications/<uuid:certification_id>/edit/', EditCertificationView.as_view(), name='edit_certification'),

    # Job Listings and Applications
    path('jobs/', JobListView.as_view(), name='job_list'),
    path('jobs/<uuid:job_id>/apply/', ApplyJobView.as_view(), name='apply_job'),
    path('applications/<uuid:application_id>/withdraw/', WithdrawApplicationView.as_view(), name='withdraw_application'),

    # Interview Management
    path('interviews/<uuid:interview_id>/instructions/', InterviewInstructionsView.as_view(), name='interview_instructions'),
    path('interviews/<uuid:interview_id>/start/', StartInterviewView.as_view(), name='start_interview'),

    # Dashboard
    path('candidates/<uuid:candidate_id>/dashboard/', DashboardView.as_view(), name='dashboard'),

    # Notifications
    path('candidates/<uuid:candidate_id>/notifications/', NotificationListView.as_view(), name='notification_list'),
    path('notifications/<uuid:notification_id>/mark-read/', MarkNotificationReadView.as_view(), name='mark_notification_read'),
]