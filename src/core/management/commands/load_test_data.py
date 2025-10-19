from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from categories.infrastructure.models import Category
from products.infrastructure.models import Product, Brand, GameType, Audience, Review, ProductImage
from cart.infrastructure.models import CartItem
from orders.infrastructure.models import Order, OrderItem
from users.infrastructure.models import User
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
import random
import requests
from django.core.files.base import ContentFile


User = get_user_model()

class Command(BaseCommand):
    help = 'Loads initial test data into the database'

    def download_image(self, url, filename):
        """Helper method to download and create an image file"""
        try:
            response = requests.get(url)
            if response.status_code == 200:
                return ContentFile(response.content, name=filename)
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Failed to download image: {e}'))
        return None

    def create_orders(self, test_user):
        """Helper method to create test orders"""
        if Order.objects.filter(user=test_user).exists():
            self.stdout.write(self.style.WARNING(f'Orders exist for user {test_user.email}, skipping'))
            return

        for status in Order.STATUS_CHOICES:
            status_code = status[0]  # Get the status code ('pending', 'processing', etc.)
            order = Order.objects.create(
                user=test_user,
                total_amount=Decimal('0'),  # Will be updated after adding items
                status=status_code
            )

            # Add 2-3 random products to each order
            products_for_order = random.sample(list(Product.objects.all()), random.randint(2, 3))
            total_amount = Decimal('0')

            for product in products_for_order:
                quantity = random.randint(1, 3)
                price = product.price
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=quantity,
                    price=price
                )
                total_amount += price * quantity

            # Update order total and add products
            order.total_amount = total_amount
            order.save()
            order.products.add(*products_for_order)

    def create_cart_items(self, user):
        """Helper method to create cart items for a user"""
        if CartItem.objects.filter(user=user).exists():
            self.stdout.write(self.style.WARNING(f'Cart items exist for user {user.email}, skipping'))
            return

        # Add 1-3 random products to user's cart
        products_for_cart = random.sample(list(Product.objects.all()), random.randint(1, 3))
        
        for product in products_for_cart:
            CartItem.objects.get_or_create(
                user=user,
                product=product,
                defaults={
                    'quantity': random.randint(1, 5)
                }
            )

    def create_test_users(self):
        """Helper method to create test users"""
        users_data = [
            {
                'email': 'admin@nicedice.com',
                'username': 'nicedice_admin',  # Changed username
                'is_staff': True,
                'is_superuser': True,
                'first_name': 'Admin',
                'last_name': 'User'
            },
            {
                'email': 'manager@nicedice.com',
                'username': 'nicedice_manager',  # Changed username
                'is_staff': True,
                'first_name': 'Manager',
                'last_name': 'User'
            },
            {
                'email': 'customer@nicedice.com',
                'username': 'nicedice_customer',  # Changed username
                'first_name': 'Regular',
                'last_name': 'Customer'
            }
        ]

        created_users = []
        for user_data in users_data:
            user, created = User.objects.get_or_create(
                email=user_data['email'],
                defaults={
                    **user_data,
                    'is_active': True
                }
            )
            if created:
                user.set_password('Secret12345')
                user.save()
            created_users.append(user)
        
        return created_users

    def create_categories(self):
        """Helper method to create test categories"""
        categories = [
            {
                'name': 'Board Games',
                'description': 'Traditional board games for all ages',
                'image': 'https://picsum.photos/800/600?random=board'
            },
            {
                'name': 'Card Games',
                'description': 'From poker to collectible card games',
                'image': 'https://picsum.photos/800/600?random=card'
            },
            {
                'name': 'Dice Games',
                'description': 'Games primarily using dice mechanics',
                'image': 'https://picsum.photos/800/600?random=dice'
            },
            {
                'name': 'Party Games',
                'description': 'Fun social games for groups',
                'image': 'https://picsum.photos/800/600?random=party'
            },
            {
                'name': 'Strategy Games',
                'description': 'Games requiring tactical thinking',
                'image': 'https://picsum.photos/800/600?random=strategy'
            }
        ]

        for category_data in categories:
            Category.objects.get_or_create(
                name=category_data['name'],
                defaults=category_data
            )
        self.stdout.write(self.style.SUCCESS('Created categories'))

    def check_existing_data(self):
        """Check if we already have data in main tables"""
        data_exists = {
            'users': User.objects.exists(),
            'categories': Category.objects.exists(),
            'products': Product.objects.exists(),
            'brands': Brand.objects.exists(),
            'audiences': Audience.objects.exists(),
            'game_types': GameType.objects.exists(),
            'reviews': Review.objects.exists(),
            'orders': Order.objects.exists(),
            'cart_items': CartItem.objects.exists(),
        }
        
        return data_exists

    def handle(self, *args, **kwargs):
        self.stdout.write('Checking existing data...')
        existing_data = self.check_existing_data()
        
        for entity, exists in existing_data.items():
            if exists:
                self.stdout.write(self.style.WARNING(f'Found existing {entity}, will skip creation'))
        
        if all(existing_data.values()):
            self.stdout.write(self.style.SUCCESS('All data exists, nothing to create'))
            return

        self.stdout.write('Creating missing test data...')
        
        # Create categories if needed
        if not existing_data['categories']:
            self.create_categories()
        
        # Create users if needed
        if not existing_data['users']:
            users = self.create_test_users()
            self.stdout.write(self.style.SUCCESS('Created test users'))
            test_user = users[0]
        else:
            test_user = User.objects.filter(is_staff=True).first()
        
        # Create audience types if needed
        if not existing_data['audiences']:
            audiences = [
                {'name': 'Kids'},
                {'name': 'Teenagers'},
                {'name': 'Adults'},
                {'name': 'Family'},
            ]
            
            for audience_data in audiences:
                Audience.objects.get_or_create(**audience_data)
            self.stdout.write(self.style.SUCCESS('Created audience types'))

        # Create game types - only name is needed
        game_types = [
            {'name': 'Strategy'},
            {'name': 'Party'},
            {'name': 'RPG'},
            {'name': 'Card Game'},
        ]
        
        for game_type in game_types:
            GameType.objects.get_or_create(**game_type)
        self.stdout.write(self.style.SUCCESS('Created game types'))

        # Create brands - only name is needed
        brands = [
            {'name': 'Hasbro'},
            {'name': 'Asmodee'},
            {'name': 'Fantasy Flight'},
            {'name': 'KOSMOS'},
            {'name': 'Days of Wonder'},
        ]
        
        for brand in brands:
            Brand.objects.get_or_create(**brand)
        self.stdout.write(self.style.SUCCESS('Created brands'))

        # Create products with correct relationships
        products = [
            {
                'name': 'Monopoly',
                'description': 'Classic property trading game',
                'price': '29.99',
                'stock': 50,
                'brand': Brand.objects.get(name='Hasbro'),
            },
            {
                'name': 'Catan',
                'description': 'Resource management and trading game',
                'price': '39.99',
                'stock': 30,
                'brand': Brand.objects.get(name='KOSMOS'),
            },
            {
                'name': 'Ticket to Ride',
                'description': 'Railway route building game',
                'price': '44.99',
                'stock': 25,
                'brand': Brand.objects.get(name='Days of Wonder'),
            },
            {
                'name': 'Pandemic',
                'description': 'Cooperative disease fighting game',
                'price': '34.99',
                'stock': 40,
                'brand': Brand.objects.get(name='Asmodee'),
            },
        ]
        
        # Update product creation to use correct Review fields
        for product_data in products:
            product, created = Product.objects.get_or_create(**product_data)
            if created:
                # Add M2M relationships
                product.types.add(GameType.objects.get(name='Strategy'))
                product.audiences.add(Audience.objects.get(name='Family'))
                product.categories.add(Category.objects.get(name='Board Games'))

                # Create product images
                ProductImage.objects.create(
                    product=product,
                    url_original=f'https://picsum.photos/800/600?random={product.id}',
                    url_lg=f'https://picsum.photos/600/400?random={product.id}',
                    url_md=f'https://picsum.photos/400/300?random={product.id}',
                    url_sm=f'https://picsum.photos/200/150?random={product.id}',
                    alt=f'{product.name} image'
                )
                
                # Create a review for the product (removed user field)
                Review.objects.get_or_create(
                    product=product,
                    rating=5,
                    comment=f'Great {product.name} game!'
                )
                
        self.stdout.write(self.style.SUCCESS('Created products with images and reviews'))

        # Create orders for test user
        self.create_orders(test_user)
        self.stdout.write(self.style.SUCCESS('Created orders with items'))

        # Create additional test users with different roles
        users_data = [
            {
                'email': 'admin@example.com',
                'username': 'example_admin',  # Changed username
                'is_staff': True,
                'is_superuser': True
            },
            {
                'email': 'manager@example.com',
                'username': 'example_manager',  # Changed username
                'is_staff': True
            }
        ]

        for user_data in users_data:
            user, created = User.objects.get_or_create(
                email=user_data['email'],
                defaults={
                    **user_data,
                    'is_active': True
                }
            )
            if created:
                user.set_password('testpass123')
                user.save()

        self.stdout.write(self.style.SUCCESS('Created additional users'))

        # Create reviews with different ratings for each product
        ratings = [3.50, 4.00, 4.50, 5.00]
        for product in Product.objects.all():
            for rating in ratings:
                Review.objects.get_or_create(
                    product=product,
                    rating=rating,
                    defaults={
                        'comment': f'{rating} star review for {product.name}',
                        'created_at': timezone.now() - timedelta(days=random.randint(1, 30))
                    }
                )
        self.stdout.write(self.style.SUCCESS('Created reviews'))

        # Create cart items for all users
        for user in User.objects.all():
            self.create_cart_items(user)
        self.stdout.write(self.style.SUCCESS('Created cart items for all users'))

        self.stdout.write(self.style.SUCCESS('Successfully created all test data'))