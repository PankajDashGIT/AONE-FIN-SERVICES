def user_roles(request):
    user = request.user
    return {
        "is_admin": user.is_authenticated and user.groups.filter(name="ADMIN").exists(),
        "is_staff_user": user.is_authenticated and user.groups.filter(name="STAFF").exists(),
    }
