from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from django.contrib.auth import get_user_model
from .models import Wish
from subscription.models import Subscription
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


def create_jwt_token(user):
    refresh = RefreshToken.for_user(user)
    return str(refresh.access_token)


class WishTests(APITestCase):
    def setUp(self) -> None:
        self.user1 = User.objects.create_user(email='test_user1@example.com')
        self.user2 = User.objects.create_user(email='test_user2@example.com')

        Subscription.objects.create(user=self.user1, subscribed_to=self.user2)

        self.ability = Wish.objects.create(
            name='Test Ability',
            author=self.user2,
            access_type='everyone'
        )

        self.token = create_jwt_token(self.user1)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + self.token)
        self.url = reverse('abilities-list')

    def test_create_ability(self) -> None:
        """test create ability"""
        url = reverse('abilities-list')
        data = {
            'name': 'New Ability',
            'access_type': 'subscribers'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Wish.objects.count(), 2)
        self.assertEqual(Wish.objects.get(pk=response.data['id']).author, self.user1)

    def test_retrieve_ability(self) -> None:
        """test retrieve ability"""
        url = reverse('abilities-detail', kwargs={'pk': self.ability.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], self.ability.name)

    def test_update_ability(self) -> None:
        """test update ability"""
        url = reverse('abilities-detail', kwargs={'pk': self.ability.pk})
        data = {'name': 'Updated Ability'}
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.ability.refresh_from_db()
        self.assertEqual(self.ability.name, 'Updated Ability')

    def test_user_abilities(self) -> None:
        """test user abilities"""
        url = reverse('abilities-user-abilities')
        response = self.client.get(url, {'user_id': self.user2.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], self.ability.name)

    def test_user_abilities_without_user(self) -> None:
        """test user abilities without user"""
        url = reverse('abilities-user-abilities')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['detail'], 'User ID parameter is required.')

    def test_user_abilities_for_nonexistent_user(self) -> None:
        """test user abilities for nonexistent user"""
        url = reverse('abilities-user-abilities')
        response = self.client.get(url, {'user_id': 1})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data['detail'], 'User with this ID does not exist.')
