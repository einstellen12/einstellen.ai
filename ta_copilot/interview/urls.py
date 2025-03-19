from django.urls import path
from . import views

urlpatterns = [
    path('start/', views.StartInterviewView.as_view(), name='start_interview'),
    path('<int:interview_id>/end/', views.EndInterviewView.as_view(), name='end_interview'),
    path('<int:interview_id>/report/generate/', views.GenerateReportView.as_view(), name='generate_report'),
    path('<int:interview_id>/questions/mark/', views.MarkQuestionView.as_view(), name='mark_question'),
    path('report/candidate/<str:candidate_id>/', views.FetchCandidateReportsView.as_view(), name='fetch_candidate_reports'),
    path('<int:interview_id>/', views.InterviewPageView.as_view(), name='interview_page'),
    path('<int:interview_id>/regenerate-link/', views.RegenerateInterviewLinkView.as_view(), name='regenerate_interview_link'),
]