from django.shortcuts import render
from closedverse_main.models import User

in_maintenance = False

class MaintenanceManagement():
    """Maintenance Management"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if(in_maintenance):
            try:
                if not(User.is_staff(request.user)):
                    return render(request, 'maintenance.html')
                else:
                    return response
            except:
                return render(request, 'maintenance.html')
        else:
            return response