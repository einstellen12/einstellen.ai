from django.urls import path
from .views import (
    CandidateSignupView, CandidateLoginView, EmployerSignupView, EmployerLoginView,
    RefreshTokenView, UserProfileView, AssignRoleView, SetupMFAView, VerifyMFAView, SocialLoginView,
    VerifyTokenView
)

urlpatterns = [
    path("candidate/signup/", CandidateSignupView.as_view(), name="candidate_signup"),
    path("candidate/login/", CandidateLoginView.as_view(), name="candidate_login"),
    path("employer/signup/", EmployerSignupView.as_view(), name="employer_signup"),
    path("employer/login/", EmployerLoginView.as_view(), name="employer_login"),
    path("refresh/", RefreshTokenView.as_view(), name="refresh"),
    path("user/", UserProfileView.as_view(), name="user_profile"),
    path("assign-role/", AssignRoleView.as_view(), name="assign_role"),
    path("mfa/setup/", SetupMFAView.as_view(), name="mfa_setup"),
    path("mfa/verify/", VerifyMFAView.as_view(), name="mfa_verify"),
    path("verify-token/", VerifyTokenView.as_view(), name="verify_token"),
    path("social-login/", SocialLoginView.as_view(), name="social_login"),
]