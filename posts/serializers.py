from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from .models import Post, PostReaction, Comment


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'is_staff', 'date_joined']
        read_only_fields = ['id', 'email', 'is_staff', 'date_joined']



class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150, min_length=3, trim_whitespace=True)
    email = serializers.EmailField(trim_whitespace=True)
    password = serializers.CharField(write_only=True, min_length=8)

    def validate_username(self, value):
        username = value.strip()
        if User.objects.filter(username__iexact=username).exists():
            raise serializers.ValidationError("A user with this username already exists.")
        return username

    def validate_email(self, value):
        email = value.strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("A user with this email address already exists.")
        return email

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value

    def create(self, validated_data):
        return User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password']
        )


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(trim_whitespace=True)
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get('email', '').strip().lower()
        password = attrs.get('password')

        if not email or not password:
            raise serializers.ValidationError("Both email and password are required.")

        user = User.objects.filter(email__iexact=email).first()
        if not user or not user.check_password(password):
            raise serializers.ValidationError("Invalid email or password.")

        if not user.is_active:
            raise serializers.ValidationError("This user account is inactive.")

        attrs['user'] = user
        return attrs


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    username = serializers.CharField(max_length=150, min_length=3, trim_whitespace=True)

    class Meta:
        model = User
        fields = ['username']

    def validate_username(self, value):
        username = value.strip()
        user = self.instance
        if User.objects.filter(username__iexact=username).exclude(pk=user.pk).exists():
            raise serializers.ValidationError("This username is already taken.")
        return username


class PostListSerializer(serializers.ModelSerializer):
    """
    Optimized lightweight serializer for post lists/feeds.
    Omits view-specific computed fields (user_reaction, is_author, updated_at)
    to save unnecessary database queries and minimize JSON payload size.
    """
    author_username = serializers.SerializerMethodField()
    likes_count = serializers.SerializerMethodField()
    dislikes_count = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            "id",
            "title",
            "content",
            "author_name",
            "author_username",
            "is_anonymous",
            "likes_count",
            "dislikes_count",
            "comments_count",
            "created_at",
        ]
        read_only_fields = fields

    def get_author_username(self, obj):
        if obj.is_anonymous:
            return "Anonymous"
        if obj.author:
            return obj.author.username
        return obj.author_name.strip() if obj.author_name else "Anonymous"

    def get_likes_count(self, obj):
        return obj.reactions.filter(reaction_type=PostReaction.REACTION_LIKE).count()

    def get_dislikes_count(self, obj):
        return obj.reactions.filter(reaction_type=PostReaction.REACTION_DISLIKE).count()

    def get_comments_count(self, obj):
        return obj.comments.count()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.is_anonymous:
            data['author_name'] = 'Anonymous'
            data['author_username'] = 'Anonymous'
        return data


class PostSerializer(serializers.ModelSerializer):
    title = serializers.CharField(
        max_length=255,
        min_length=3,
        trim_whitespace=True
    )
    content = serializers.CharField(
        min_length=5,
        trim_whitespace=True
    )
    author_username = serializers.SerializerMethodField()
    likes_count = serializers.SerializerMethodField()
    dislikes_count = serializers.SerializerMethodField()
    user_reaction = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()
    is_author = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            "id",
            "title",
            "content",
            "author_name",
            "author_username",
            "is_anonymous",
            "likes_count",
            "dislikes_count",
            "user_reaction",
            "comments_count",
            "is_author",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "author_username",
            "likes_count",
            "dislikes_count",
            "user_reaction",
            "comments_count",
            "is_author",
            "created_at",
            "updated_at",
        ]

    def get_author_username(self, obj):
        if obj.is_anonymous:
            return "Anonymous"
        if obj.author:
            return obj.author.username
        return obj.author_name.strip() if obj.author_name else "Anonymous"

    def get_likes_count(self, obj):
        return obj.reactions.filter(reaction_type=PostReaction.REACTION_LIKE).count()

    def get_dislikes_count(self, obj):
        return obj.reactions.filter(reaction_type=PostReaction.REACTION_DISLIKE).count()

    def get_user_reaction(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            reaction = obj.reactions.filter(user=request.user).first()
            return reaction.reaction_type if reaction else None
        return None

    def get_comments_count(self, obj):
        return obj.comments.count()

    def get_is_author(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated and obj.author:
            return obj.author == request.user
        return False

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.is_anonymous:
            data['author_name'] = 'Anonymous'
            data['author_username'] = 'Anonymous'
        return data



class CommentSerializer(serializers.ModelSerializer):
    author_username = serializers.SerializerMethodField()
    is_author = serializers.SerializerMethodField()
    replies = serializers.SerializerMethodField()
    content = serializers.CharField(min_length=1, trim_whitespace=True)

    class Meta:
        model = Comment
        fields = [
            "id",
            "post",
            "parent",
            "content",
            "author_username",
            "is_anonymous",
            "is_author",
            "replies",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "author_username",
            "is_author",
            "replies",
            "created_at",
            "updated_at",
        ]

    def get_author_username(self, obj):
        if obj.is_anonymous:
            return "Anonymous"
        if obj.author:
            return obj.author.username
        return "Anonymous"

    def get_is_author(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated and obj.author:
            return obj.author == request.user
        return False

    def get_replies(self, obj):
        # Nested serialization of child replies
        child_replies = obj.replies.all().order_by('created_at')
        if not child_replies.exists():
            return []
        serializer = CommentSerializer(child_replies, many=True, context=self.context)
        return serializer.data

    def validate(self, attrs):
        parent = attrs.get('parent')
        post = attrs.get('post')

        if parent:
            if self.instance and parent.id == self.instance.id:
                raise serializers.ValidationError({"parent": "A comment cannot reply to itself."})

            if post and parent.post_id != post.id:
                raise serializers.ValidationError({"parent": "Parent comment does not belong to this post."})
        return attrs

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.is_anonymous:
            data['author_username'] = 'Anonymous'
        return data


class UserActivityCommentSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for user's profile activity list.
    Avoids recursive serialization of the child replies tree.
    """
    class Meta:
        model = Comment
        fields = [
            "id",
            "post",
            "content",
            "is_anonymous",
            "created_at",
        ]
        read_only_fields = fields


class PostReactionSerializer(serializers.Serializer):
    reaction_type = serializers.ChoiceField(choices=['like', 'dislike'])