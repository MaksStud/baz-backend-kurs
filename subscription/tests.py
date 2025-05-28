from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from .models import Subscription
from django.contrib.auth import get_user_model

User = get_user_model()


class SubscriptionTests(APITestCase):
    def setUp(self) -> None:
        """data set for testing"""
        self.user1 = User.objects.create_user(email='test_user1@example.com', password='password')
        self.user2 = User.objects.create_user(email='test_user2@example.com', password='password')
        self.client.force_authenticate(user=self.user1)
        self.url_subscribe = reverse('subscribe')
        self.url_unsubscribe = reverse('unsubscribe')
        self.url_subscriptions = reverse('subscriptions')
        self.url_subscribers = reverse('subscribers')

    def test_subscribe(self) -> None:
        """test subscribe"""
        data = {'subscribed_to_id': self.user2.id}
        response = self.client.post(self.url_subscribe, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Subscription.objects.filter(user=self.user1, subscribed_to=self.user2).exists())

    def test_subscribe_self(self) -> None:
        """test subscribe self"""
        data = {'subscribed_to_id': self.user1.id}
        response = self.client.post(self.url_subscribe, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("You cannot subscribe to yourself.", response.data['detail'])

    def test_already_subscribed(self) -> None:
        """test already subscribed"""
        Subscription.objects.create(user=self.user1, subscribed_to=self.user2)
        data = {'subscribed_to_id': self.user2.id}
        response = self.client.post(self.url_subscribe, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("You are already subscribed to this user.", response.data['detail'])

    def test_unsubscribe(self) -> None:
        """test unsubscribe"""
        Subscription.objects.create(user=self.user1, subscribed_to=self.user2)
        data = {'subscribed_to_id': self.user2.id}
        response = self.client.delete(self.url_unsubscribe, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Subscription.objects.filter(user=self.user1, subscribed_to=self.user2).exists())

    def test_get_subscriptions(self) -> None:
        """test get subscriptions"""
        Subscription.objects.create(user=self.user1, subscribed_to=self.user2)
        response = self.client.get(self.url_subscriptions)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertIn('subscriptions', response.data)

    def test_get_subscribers(self) -> None:
        """test get subscribers"""
        Subscription.objects.create(user=self.user2, subscribed_to=self.user1)
        response = self.client.get(self.url_subscribers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertIn('subscribers', response.data)
