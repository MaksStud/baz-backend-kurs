from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from rest_framework_simplejwt.tokens import RefreshToken
from .models import Brand, Wish
from django.contrib.auth import get_user_model

User = get_user_model()


def create_jwt_token(user: User) -> str:
    refresh = RefreshToken.for_user(user)
    return str(refresh.access_token)


class BrandViewSetTests(APITestCase):
    """Test for Brand model"""
    @classmethod
    def setUpTestData(cls) -> None:
        """Data for testing"""
        # Create users
        cls.user1 = User.objects.create_user(email='test_user1@example.com')
        cls.user2 = User.objects.create_user(email='test_user2@example.com')

        # Create abilities
        cls.ability1 = Wish.objects.create(
            name='Ability1',
            author=cls.user2,
            access_type='everyone'
        )
        cls.ability2 = Wish.objects.create(
            name='Ability2',
            author=cls.user2,
            access_type='everyone'
        )

        # Create Brand instances
        cls.brand1 = Brand.objects.create(
            slug='brand-1',
            name='Brand 1',
            nickname='Nick 1',
            description='Description 1',
            photo='path/to/photo1.jpg'
        )
        cls.brand1.abilities.set([cls.ability1, cls.ability2])

        cls.brand2 = Brand.objects.create(
            slug='brand-2',
            name='Brand 2',
            nickname='Nick 2',
            description='Description 2',
            photo='path/to/photo2.jpg'
        )

    def setUp(self) -> None:
        # Set up JWT token authentication for user1
        self.token = create_jwt_token(self.user1)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + self.token)

    def test_list_brands(self) -> None:
        """test list brands"""
        url = reverse('brand-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_brand_detail(self) -> None:
        """test get brand"""
        url = reverse('brand-detail', args=[self.brand1.slug])  # Ensure 'brand-detail' matches your route name
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_paginated_abilities(self) -> None:
        """test paginated abilities"""
        url = reverse('brand-paginated-abilities', args=[self.brand1.slug])
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_brand_access_without_authentication(self) -> None:
        """test brand access without authentication"""
        self.client.credentials()  # Remove credentials
        url = reverse('brand-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

