from rest_framework import permissions


class IsAuthorOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow authors of an object to edit or delete it.
    Read permissions are allowed to any request (GET, HEAD, OPTIONS).
    """

    def has_object_permission(self, request, view, obj):
        # Read-only operations are always permitted
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write operations require authentication and ownership match
        if not request.user or not request.user.is_authenticated:
            return False

        # If post has no author linked (legacy post), disallow unauthenticated modifications
        return obj.author is not None and obj.author == request.user
