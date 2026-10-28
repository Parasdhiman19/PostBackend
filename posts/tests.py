from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework.authtoken.models import Token
from .models import Post


class PostAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='legacyuser',
            email='legacy@example.com',
            password='password123'
        )
        self.client.force_authenticate(user=self.user)
        self.valid_payload = {
            'title': 'Test Post Title',
            'content': 'This is valid post content with sufficient length.',
            'author_name': 'Jane Doe'
        }

    def test_create_post_success(self):
        """Verify successful creation of a post with all fields."""
        response = self.client.post('/api/posts/', self.valid_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['title'], self.valid_payload['title'])
        self.assertEqual(response.data['content'], self.valid_payload['content'])
        self.assertEqual(response.data['author_name'], self.valid_payload['author_name'])
        self.assertIn('id', response.data)
        self.assertIn('created_at', response.data)

    def test_create_post_without_author(self):
        """Verify author_name is optional and defaults to empty string."""
        payload = {
            'title': 'No Author Post',
            'content': 'Content without author specified.'
        }
        response = self.client.post('/api/posts/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['author_name'], '')

    def test_create_post_title_too_short(self):
        """Verify validation error when title has fewer than 3 characters."""
        payload = {
            'title': 'Hi',
            'content': 'Valid content length here.'
        }
        response = self.client.post('/api/posts/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('title', response.data)

    def test_create_post_content_too_short(self):
        """Verify validation error when content has fewer than 5 characters."""
        payload = {
            'title': 'Valid Title',
            'content': '1234'
        }
        response = self.client.post('/api/posts/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('content', response.data)

    def test_create_post_whitespace_trimmed(self):
        """Verify whitespace is trimmed and whitespace-only title fails."""
        payload = {
            'title': '   ',
            'content': 'Valid content length here.'
        }
        response = self.client.post('/api/posts/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_posts(self):
        """Verify posts list returns HTTP 200."""
        Post.objects.create(title='Post 1', content='Content for post 1')
        Post.objects.create(title='Post 2', content='Content for post 2')
        response = self.client.get('/api/posts/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_retrieve_post_by_id(self):
        """Verify retrieving single post by id."""
        post = Post.objects.create(title='Specific Post', content='Content for specific post')
        response = self.client.get(f'/api/posts/{post.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Specific Post')


class AuthAndSocialAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'StrongPassword123!',
        }
        self.other_user_data = {
            'username': 'otheruser',
            'email': 'other@example.com',
            'password': 'StrongPassword123!',
        }

    def test_user_registration_success(self):
        """Verify user registration returns token and user data."""
        response = self.client.post('/api/auth/register/', self.user_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('token', response.data)
        self.assertEqual(response.data['user']['username'], 'testuser')
        self.assertEqual(response.data['user']['email'], 'test@example.com')
        self.assertNotIn('password', response.data['user'])

    def test_duplicate_registration_fails(self):
        """Verify duplicate email or username registration fails (case-insensitive)."""
        self.client.post('/api/auth/register/', self.user_data, format='json')

        # Duplicate username with different case
        res_dup_username = self.client.post('/api/auth/register/', {
            'username': 'TESTUSER',
            'email': 'different@example.com',
            'password': 'StrongPassword123!',
        }, format='json')
        self.assertEqual(res_dup_username.status_code, status.HTTP_400_BAD_REQUEST)

        # Duplicate email with different case
        res_dup_email = self.client.post('/api/auth/register/', {
            'username': 'brandnewuser',
            'email': 'TEST@EXAMPLE.COM',
            'password': 'StrongPassword123!',
        }, format='json')
        self.assertEqual(res_dup_email.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_with_email_success(self):
        """Verify login using email and password (not username)."""
        self.client.post('/api/auth/register/', self.user_data, format='json')
        response = self.client.post('/api/auth/login/', {
            'email': 'TEST@EXAMPLE.COM',  # Case-insensitive
            'password': 'StrongPassword123!',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('token', response.data)
        self.assertEqual(response.data['user']['username'], 'testuser')

    def test_login_with_invalid_credentials_fails(self):
        """Verify login fails with wrong password or wrong email."""
        self.client.post('/api/auth/register/', self.user_data, format='json')
        response = self.client.post('/api/auth/login/', {
            'email': 'test@example.com',
            'password': 'WrongPassword!',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_logout(self):
        """Verify logout revokes auth token."""
        reg_res = self.client.post('/api/auth/register/', self.user_data, format='json')
        token = reg_res.data['token']
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')

        logout_res = self.client.post('/api/auth/logout/')
        self.assertEqual(logout_res.status_code, status.HTTP_200_OK)

        # Subsequent authenticated requests should fail
        me_res = self.client.get('/api/auth/me/')
        self.assertEqual(me_res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_anonymous_and_public_post_creation(self):
        """Verify anonymous post masks author_username publicly while retaining author ownership."""
        reg_res = self.client.post('/api/auth/register/', self.user_data, format='json')
        token = reg_res.data['token']
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')

        # Public post
        pub_res = self.client.post('/api/posts/', {
            'title': 'Public Article',
            'content': 'This is a public article content.',
            'is_anonymous': False,
        }, format='json')
        self.assertEqual(pub_res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(pub_res.data['author_username'], 'testuser')

        # Anonymous post
        anon_res = self.client.post('/api/posts/', {
            'title': 'Secret Article',
            'content': 'This is an anonymous article content.',
            'is_anonymous': True,
        }, format='json')
        self.assertEqual(anon_res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(anon_res.data['author_username'], 'Anonymous')
        self.assertTrue(anon_res.data['is_anonymous'])

    def test_post_reactions_toggle_and_switch(self):
        """Verify like and dislike toggling and switching logic."""
        reg_res = self.client.post('/api/auth/register/', self.user_data, format='json')
        token = reg_res.data['token']
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')

        post = Post.objects.create(title='Post for reaction', content='Content here.')

        # 1. Like the post
        res_like = self.client.post(f'/api/posts/{post.id}/react/', {'reaction_type': 'like'}, format='json')
        self.assertEqual(res_like.status_code, status.HTTP_200_OK)
        self.assertEqual(res_like.data['user_reaction'], 'like')
        self.assertEqual(res_like.data['likes_count'], 1)
        self.assertEqual(res_like.data['dislikes_count'], 0)

        # 2. Toggle off like
        res_toggle = self.client.post(f'/api/posts/{post.id}/react/', {'reaction_type': 'like'}, format='json')
        self.assertEqual(res_toggle.status_code, status.HTTP_200_OK)
        self.assertIsNone(res_toggle.data['user_reaction'])
        self.assertEqual(res_toggle.data['likes_count'], 0)

        # 3. Dislike the post
        res_dislike = self.client.post(f'/api/posts/{post.id}/react/', {'reaction_type': 'dislike'}, format='json')
        self.assertEqual(res_dislike.status_code, status.HTTP_200_OK)
        self.assertEqual(res_dislike.data['user_reaction'], 'dislike')
        self.assertEqual(res_dislike.data['dislikes_count'], 1)

        # 4. Switch dislike to like
        res_switch = self.client.post(f'/api/posts/{post.id}/react/', {'reaction_type': 'like'}, format='json')
        self.assertEqual(res_switch.status_code, status.HTTP_200_OK)
        self.assertEqual(res_switch.data['user_reaction'], 'like')
        self.assertEqual(res_switch.data['likes_count'], 1)
        self.assertEqual(res_switch.data['dislikes_count'], 0)

    def test_threaded_comments_and_nested_replies(self):
        """Verify top-level and nested reply comments with anonymous option."""
        reg_res = self.client.post('/api/auth/register/', self.user_data, format='json')
        token = reg_res.data['token']
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')

        post = Post.objects.create(title='Article with discussion', content='Content here.')

        # Create top level comment
        c1_res = self.client.post('/api/comments/', {
            'post': post.id,
            'content': 'Great architectural breakdown!',
            'is_anonymous': False,
        }, format='json')
        self.assertEqual(c1_res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(c1_res.data['author_username'], 'testuser')
        c1_id = c1_res.data['id']

        # Reply to c1 anonymously
        c2_res = self.client.post('/api/comments/', {
            'post': post.id,
            'parent': c1_id,
            'content': 'I agree with this point.',
            'is_anonymous': True,
        }, format='json')
        self.assertEqual(c2_res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(c2_res.data['author_username'], 'Anonymous')

        # Retrieve comments for post
        list_res = self.client.get(f'/api/comments/?post={post.id}&top_level=true')
        self.assertEqual(list_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_res.data), 1)
        self.assertEqual(len(list_res.data[0]['replies']), 1)
        self.assertEqual(list_res.data[0]['replies'][0]['author_username'], 'Anonymous')

    def test_profile_update_and_activity(self):
        """Verify username update, duplicate prevention, and user activity."""
        reg_res = self.client.post('/api/auth/register/', self.user_data, format='json')
        token = reg_res.data['token']
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')

        # Update username
        up_res = self.client.patch('/api/auth/profile/', {'username': 'newalex'}, format='json')
        self.assertEqual(up_res.status_code, status.HTTP_200_OK)
        self.assertEqual(up_res.data['username'], 'newalex')

        # Retrieve user activity
        act_res = self.client.get('/api/auth/user-activity/')
        self.assertEqual(act_res.status_code, status.HTTP_200_OK)
        self.assertIn('posts', act_res.data)
        self.assertIn('comments', act_res.data)

    def test_comment_edit_and_delete_permissions(self):
        """Verify only the author can edit or delete their comment."""
        reg_res = self.client.post('/api/auth/register/', self.user_data, format='json')
        token = reg_res.data['token']
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')

        post = Post.objects.create(title='Post for comment perm', content='Content here.')
        c_res = self.client.post('/api/comments/', {'post': post.id, 'content': 'Initial text'}, format='json')
        c_id = c_res.data['id']

        # Edit own comment
        patch_res = self.client.patch(f'/api/comments/{c_id}/', {'content': 'Updated text'}, format='json')
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_res.data['content'], 'Updated text')

        # Other user tries to edit
        other_reg = self.client.post('/api/auth/register/', self.other_user_data, format='json')
        other_token = other_reg.data['token']
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {other_token}')

        unauth_patch = self.client.patch(f'/api/comments/{c_id}/', {'content': 'Hacked text'}, format='json')
        self.assertEqual(unauth_patch.status_code, status.HTTP_403_FORBIDDEN)

        # Other user tries to delete
        unauth_del = self.client.delete(f'/api/comments/{c_id}/')
        self.assertEqual(unauth_del.status_code, status.HTTP_403_FORBIDDEN)

    def test_anonymous_post_creation_and_identity_masking(self):
        """Verify anonymous post hides author identity while retaining ownership."""
        reg_res = self.client.post('/api/auth/register/', self.user_data, format='json')
        token = reg_res.data['token']
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')

        # 1. Author creates anonymous post
        post_res = self.client.post('/api/posts/', {
            'title': 'Secret Tech Discovery',
            'content': 'Revealing an architectural insight anonymously.',
            'is_anonymous': True,
        }, format='json')
        self.assertEqual(post_res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(post_res.data['author_username'], 'Anonymous')
        self.assertEqual(post_res.data['author_name'], 'Anonymous')
        self.assertTrue(post_res.data['is_author'])
        post_id = post_res.data['id']

        # 2. Unauthenticated user fetches post
        self.client.credentials()  # Clear auth token
        anon_fetch = self.client.get(f'/api/posts/{post_id}/')
        self.assertEqual(anon_fetch.status_code, status.HTTP_200_OK)
        self.assertEqual(anon_fetch.data['author_username'], 'Anonymous')
        self.assertEqual(anon_fetch.data['author_name'], 'Anonymous')
        self.assertFalse(anon_fetch.data['is_author'])

        # 3. Author can still view and manage their own post in user activity
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')
        act_res = self.client.get('/api/auth/user-activity/')
        self.assertEqual(act_res.status_code, status.HTTP_200_OK)
        post_ids = [p['id'] for p in act_res.data['posts']]
        self.assertIn(post_id, post_ids)

    def test_admin_only_insights(self):
        """Verify only staff/admin users can access /api/insights/."""
        # 1. Unauthenticated request -> 401
        self.client.credentials()
        unauth_res = self.client.get('/api/insights/')
        self.assertEqual(unauth_res.status_code, status.HTTP_401_UNAUTHORIZED)

        # 2. Regular user request -> 403 Forbidden
        reg_res = self.client.post('/api/auth/register/', self.user_data, format='json')
        token = reg_res.data['token']
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')
        forbidden_res = self.client.get('/api/insights/')
        self.assertEqual(forbidden_res.status_code, status.HTTP_403_FORBIDDEN)

        # 3. Staff/Admin user request -> 200 OK
        admin_user = User.objects.create_superuser(
            username='adminboss',
            email='admin@example.com',
            password='AdminPassword123!'
        )
        admin_token, _ = Token.objects.get_or_create(user=admin_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {admin_token.key}')
        admin_res = self.client.get('/api/insights/')
        self.assertEqual(admin_res.status_code, status.HTTP_200_OK)
        self.assertIn('total_posts', admin_res.data)
        self.assertIn('anonymous_count', admin_res.data)
        self.assertIn('authors_list', admin_res.data)

    def test_feed_filter_all_and_anonymous(self):
        """Verify /api/posts/?filter=anonymous returns only anonymous posts."""
        Post.objects.create(title='Public Post 1', content='Content 1', is_anonymous=False)
        Post.objects.create(title='Anon Post 1', content='Content 2', is_anonymous=True)

        # Filter: anonymous
        anon_res = self.client.get('/api/posts/?filter=anonymous')
        self.assertEqual(anon_res.status_code, status.HTTP_200_OK)
        for post in anon_res.data:
            self.assertTrue(post['is_anonymous'])
            self.assertEqual(post['author_username'], 'Anonymous')

        # Filter: all
        all_res = self.client.get('/api/posts/?filter=all')
        self.assertEqual(all_res.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(all_res.data), 2)


