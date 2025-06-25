from rest_framework import permissions


class IsCompanyMember(permissions.BasePermission):
    """
    Permission to check if user is a member of the company
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Check if user belongs to the same company as the object
        if hasattr(obj, 'company'):
            return request.user.company == obj.company
        elif hasattr(obj, 'users'):  # For Company model
            return request.user in obj.users.all()
        return False


class IsCompanyAdminOrReadOnly(permissions.BasePermission):
    """
    Permission to allow company admins to edit, others to read only
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Read permissions for any authenticated user in the company
        if request.method in permissions.SAFE_METHODS:
            return self._is_company_member(request.user, obj)
        
        # Write permissions only for company admins
        return self._is_company_admin(request.user, obj)

    def _is_company_member(self, user, obj):
        if hasattr(obj, 'company'):
            return user.company == obj.company
        elif hasattr(obj, 'users'):  # For Company model
            return user in obj.users.all()
        return False

    def _is_company_admin(self, user, obj):
        if not self._is_company_member(user, obj):
            return False
        return user.role in ['owner', 'admin']


class IsCompanyOwner(permissions.BasePermission):
    """
    Permission to check if user is the owner of the company
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'company'):
            return (request.user.company == obj.company and 
                   request.user.role == 'owner')
        elif hasattr(obj, 'users'):  # For Company model
            return (request.user in obj.users.all() and 
                   request.user.role == 'owner')
        return False


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Permission to allow owners of an object to edit it, others read only
    """
    def has_object_permission(self, request, view, obj):
        # Read permissions for any authenticated user
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions only for the owner
        return obj.owner == request.user


class IsSameUserOrAdmin(permissions.BasePermission):
    """
    Permission to allow users to edit their own data, or admins to edit any
    """
    def has_object_permission(self, request, view, obj):
        # Check if it's the same user or a company admin
        if obj == request.user:
            return True
        
        if (request.user.company == obj.company and 
            request.user.role in ['owner', 'admin']):
            return True
        
        return False


class IsBridgeManager(permissions.BasePermission):
    """
    Permission for users who can manage bridges
    """
    def has_permission(self, request, view):
        return (request.user and 
                request.user.is_authenticated and
                request.user.role in ['owner', 'admin', 'manager'])

    def has_object_permission(self, request, view, obj):
        return (request.user.company == obj.company and 
                request.user.role in ['owner', 'admin', 'manager'])


class IsAIEnabled(permissions.BasePermission):
    """
    Permission to check if AI features are enabled for the company
    """
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        
        if not request.user.company:
            return False
        
        company_settings = getattr(request.user.company, 'settings', None)
        if not company_settings:
            return False
        
        return company_settings.ai_enabled


class HasAPIAccess(permissions.BasePermission):
    """
    Permission to check if user has API access
    """
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        
        # Check if user's company has an active subscription
        if request.user.company:
            return request.user.company.status == 'active'
        
        return False
