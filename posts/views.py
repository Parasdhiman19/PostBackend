from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAuthenticatedOrReadOnly, IsAdminUser
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from django.db import transaction
from django.db.models import Q
from django.utils import timezone


from .models import Post, PostReaction, Comment
from .serializers import (
    PostSerializer,
    PostListSerializer,
    CommentSerializer,
    UserActivityCommentSerializer,
    RegisterSerializer,
    LoginSerializer,
    UserSerializer,
    UserProfileUpdateSerializer,
    PostReactionSerializer,
)
from .permissions import IsAuthorOrReadOnly


# ─── Authentication Views ──────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([AllowAny])
def register_view(request):
    """Register a new user with email, unique username, and password."""
    serializer = RegisterSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user': UserSerializer(user).data
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """Authenticate a user using email and password."""
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.validated_data['user']
        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user': UserSerializer(user).data
        }, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """Revoke user authentication token."""
    try:
        request.user.auth_token.delete()
    except (AttributeError, Token.DoesNotExist):
        pass
    return Response({'message': 'Successfully logged out.'}, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me_view(request):
    """Retrieve currently authenticated user information."""
    serializer = UserSerializer(request.user)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def profile_update_view(request):
    """Update profile information (e.g. username)."""
    serializer = UserProfileUpdateSerializer(request.user, data=request.data, partial=True)
    if serializer.is_valid():
        user = serializer.save()
        return Response(UserSerializer(user).data, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_activity_view(request):
    """Return user's own posts and comments for their Settings/Profile view."""
    posts = Post.objects.filter(author=request.user).order_by('-created_at')
    comments = Comment.objects.filter(author=request.user).select_related('post').order_by('-created_at')

    post_serializer = PostListSerializer(posts, many=True, context={'request': request})
    comment_serializer = UserActivityCommentSerializer(comments, many=True, context={'request': request})

    return Response({
        'posts': post_serializer.data,
        'comments': comment_serializer.data,
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def insights_view(request):
    """Admin-only publication metrics and analytics endpoint."""
    posts = Post.objects.all().select_related('author').prefetch_related('reactions', 'comments')
    total_posts = posts.count()

    total_words = 0
    author_counts = {}
    for p in posts:
        words = len(p.content.split()) if p.content else 0
        total_words += words

        if p.is_anonymous:
            author_label = 'Anonymous'
        elif p.author:
            author_label = p.author.username
        else:
            author_label = p.author_name.strip() if p.author_name else 'Anonymous'
        author_counts[author_label] = author_counts.get(author_label, 0) + 1

    avg_words_per_post = round(total_words / total_posts) if total_posts > 0 else 0
    total_reading_time_min = max(1, round(total_words / 200))

    now = timezone.now()
    past_24h = now - timezone.timedelta(hours=24)
    past_week = now - timezone.timedelta(days=7)

    past_24h_count = posts.filter(created_at__gte=past_24h).count()
    past_week_count = posts.filter(created_at__gte=past_week).count()
    anonymous_count = posts.filter(is_anonymous=True).count()
    total_comments = Comment.objects.count()
    total_reactions = PostReaction.objects.count()

    authors_list = [
        {
            'name': name,
            'count': count,
            'pct': round((count / total_posts) * 100) if total_posts > 0 else 0
        }
        for name, count in sorted(author_counts.items(), key=lambda x: x[1], reverse=True)
    ]

    public_count = total_posts - anonymous_count
    anon_pct = round((anonymous_count / total_posts) * 100) if total_posts > 0 else 0

    return Response({
        'total_posts': total_posts,
        'total_words': total_words,
        'avg_words_per_post': avg_words_per_post,
        'total_reading_time_min': total_reading_time_min,
        'authors_list': authors_list,
        'authors': authors_list,
        'past_24h_count': past_24h_count,
        'past_24h_posts': past_24h_count,
        'past_week_count': past_week_count,
        'past_week_posts': past_week_count,
        'anonymous_count': anonymous_count,
        'anonymous_posts': anonymous_count,
        'public_posts': public_count,
        'anonymous_percentage': anon_pct,
        'total_comments': total_comments,
        'total_reactions': total_reactions,
    }, status=status.HTTP_200_OK)


# ─── Post ViewSet ──────────────────────────────────────────────────────

class PostViewSet(viewsets.ModelViewSet):
    serializer_class = PostSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, IsAuthorOrReadOnly]

    def get_serializer_class(self):
        if self.action == 'list':
            return PostListSerializer
        return PostSerializer

    def get_queryset(self):
        qs = Post.objects.all().select_related('author').prefetch_related('reactions', 'comments')
        filter_param = self.request.query_params.get('filter')
        search_query = self.request.query_params.get('search')

        # 2 clear choices: 'all' or 'anonymous'
        if filter_param == 'anonymous':
            qs = qs.filter(is_anonymous=True)

        if search_query:
            qs = qs.filter(
                Q(title__icontains=search_query) |
                Q(content__icontains=search_query) |
                Q(author_name__icontains=search_query) |
                Q(author__username__icontains=search_query)
            )

        return qs.order_by('-created_at')


    def perform_create(self, serializer):
        if self.request.user.is_authenticated:
            is_anon = serializer.validated_data.get('is_anonymous', False)
            author_name = serializer.validated_data.get('author_name', '')
            serializer.save(author=self.request.user, author_name=author_name, is_anonymous=is_anon)
        else:
            # Backwards compatibility for legacy tests / public post creation
            serializer.save()

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def react(self, request, pk=None):
        """Like or dislike a post atomically. Toggles off if identical, switches if different."""
        post = self.get_object()
        serializer = PostReactionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        reaction_type = serializer.validated_data['reaction_type']

        with transaction.atomic():
            existing = PostReaction.objects.select_for_update().filter(post=post, user=request.user).first()
            if existing:
                if existing.reaction_type == reaction_type:
                    # Toggle off
                    existing.delete()
                    user_reaction = None
                    action_status = 'removed'
                else:
                    # Switch reaction
                    existing.reaction_type = reaction_type
                    existing.save()
                    user_reaction = reaction_type
                    action_status = 'switched'
            else:
                PostReaction.objects.create(post=post, user=request.user, reaction_type=reaction_type)
                user_reaction = reaction_type
                action_status = 'added'

        likes_count = post.reactions.filter(reaction_type=PostReaction.REACTION_LIKE).count()
        dislikes_count = post.reactions.filter(reaction_type=PostReaction.REACTION_DISLIKE).count()

        return Response({
            'status': action_status,
            'user_reaction': user_reaction,
            'likes_count': likes_count,
            'dislikes_count': dislikes_count,
        }, status=status.HTTP_200_OK)


# ─── Comment ViewSet ───────────────────────────────────────────────────

class CommentViewSet(viewsets.ModelViewSet):
    queryset = Comment.objects.all().select_related('author', 'post')
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, IsAuthorOrReadOnly]

    def get_queryset(self):
        qs = super().get_queryset()
        post_id = self.request.query_params.get('post')
        top_level_only = self.request.query_params.get('top_level')

        if post_id:
            qs = qs.filter(post_id=post_id)
        if top_level_only == 'true':
            qs = qs.filter(parent__isnull=True)

        return qs.order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

