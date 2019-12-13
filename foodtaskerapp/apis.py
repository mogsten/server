from django.http import JsonResponse
import json
import logging
from django.views.decorators.csrf import csrf_exempt

from oauth2_provider.models import AccessToken
from django.utils import timezone
from foodtaskerapp.models import Restaurant, Meal, Order, OrderDetails, Driver, Modifier
from foodtaskerapp.serializers import RestaurantSerializer, MealSerializer, OrderSerializer
from collections import defaultdict


import stripe
from foodtasker.settings import STRIPE_API_KEY

stripe.api_key = STRIPE_API_KEY

def customer_get_restaurants(request):
    restaurants = RestaurantSerializer(
        Restaurant.objects.all().order_by("-id"),
        many = True,
        context = {"request": request}
    ).data

    return JsonResponse({"restaurants": restaurants})


def customer_get_meals(request, restaurant_id):
    meals = MealSerializer(
    Meal.objects.filter(restaurant_id = restaurant_id).order_by("-id"),
    many = True,
    context = {"request": request}
    ).data

    return JsonResponse({"meals": meals})

@csrf_exempt
def customer_add_order(request):
    """
        params:
            access_token
            restaurant_id
            address
            order_details (json format)
            phone_no
    """
    if request.method == "POST":
        # Get Token
        access_token = AccessToken.objects.get(token = request.POST.get("access_token"), expires__gt = timezone.now())

        # Get Profile from token

        customer = access_token.user.customer

        # GET STRIPE token
        stripe_token = request.POST["stripe_token"]

        #GET PHONE NUMBER AND ASSIGN TO CUSTOMER
        #I tried to do this, but it did not work :(
        #customer.phone = request.POST["phone_no"]

        # Check whether customer has any order that is not delivered

        if Order.objects.filter(customer = customer).exclude(status = Order.DELIVERED):
            return JsonResponse({"status": "fail", "error": "Your Last Order must be completed."})


        # Check the address
        if not request.POST["address"]:
            return JsonResponse({"status": "failed", "error": "Address is required"})


        # Get Order Details
        order_details = json.loads(request.POST["order_details"])

        order_total = 0.00
        shipping_total = 5.00
        order_final_payment_price = 0.00
        for meal in order_details:
            order_total += Meal.objects.get(id = meal["meal_id"]).price * meal["quantity"]
            order_converted_total = int(order_total) # Convert Price to Int and Send to Stripe
            
            if order_converted_total < 50:
                shipping_total = 5
                order_final_payment_price = int(order_converted_total + shipping_total)
                logging.error(order_final_payment_price)
                logging.warning(shipping_total)
               
            if order_converted_total > 50:
                shipping_total = 0
                order_final_payment_price = int(order_converted_total + shipping_total)
                logging.error(order_final_payment_price)
                logging.warning(shipping_total)

        if len(order_details) > 0:
            
            #Additional Step before ordering - Convert Order Final Price to Int
            order_finalPrice = int(order_final_payment_price)
            logging.warning('ORDER FINAL PRICE %s', order_finalPrice)

            # Step 1: Create a charge: This will Charge Customers Card
            charge = stripe.Charge.create(
                amount = order_finalPrice * 100, # Amount in Cents
                currency = "aud",
                source = stripe_token,
                description = "B!te Order"
            )

            if charge.status != "failed":
                # Step two - Create Order
                order = Order.objects.create(
                customer = customer,
                restaurant_id = request.POST["restaurant_id"],
                total = order_finalPrice,
                status = Order.PREPARING,
                address = request.POST["address"]
                )

                #step two - Create Order Details

                for meal in order_details:
                    OrderDetails.objects.create(
                        order = order,
                        meal_id = meal["meal_id"],
                        quantity = meal["quantity"],
                        sub_total = Meal.objects.get(id = meal["meal_id"]).price * meal["quantity"]

                    )

                return JsonResponse({"status": "success"})

            else:
                return JsonResponse({"status": "failed", "error": "Failed to Connect to Payment Gateway"})




def customer_get_latest_order(request):
    access_token = AccessToken.objects.get(token = request.GET.get("access_token"), expires__gt = timezone.now())

    customer = access_token.user.customer
    order = OrderSerializer(Order.objects.filter(customer = customer).last()).data

    return JsonResponse({"order": order})


def restaurant_order_notification(request, last_request_time):
    notification = Order.objects.filter(restaurant = request.user.restaurant,
    created_at__gt = last_request_time).count()

    return JsonResponse({"notification": notification})


def customer_driver_location(request):
    access_token = AccessToken.objects.get(token = request.GET.get("access_token"), expires__gt = timezone.now())

    customer = access_token.user.customer

    # Get Driver Assigned to Job's location
    current_order = Order.objects.filter(customer = customer, status = Order.ONTHEWAY).last()
    location = current_order.driver.location

    return JsonResponse({"location": location})




#############
# DRIVER API FUNCTIONS
#############

def driver_get_ready_orders(request):
    '''
    Get orders which are ready to be picked. Restaurant should be within 5km
    of the driver's location
    :param request: Django request object
    :return: List of orders which are ready
    '''
    latitude = request.GET.get('latitude')
    longitude = request.GET.get('longitude')

    # return error if latitude and longitude are not provided
    if not (latitude and longitude):
        return JsonResponse({
            'status': 'failed',
            'error': 'Driver co-ordinates required'
        })
    latitude = float(latitude)
    longitude = float(longitude)

    restaurants = Restaurant.objects.all()
    nearby_restaurants = [restaurant for restaurant in restaurants if restaurant.get_distance(latitude, longitude) <= 5]

    orders = OrderSerializer(
        Order.objects.filter(status=Order.READY, driver=None, restaurant__in=nearby_restaurants).order_by("-id"),
        many=True).data
    return JsonResponse({"orders": orders})

@csrf_exempt
def driver_pick_order(request):
    if request.method == "POST":
        access_token = AccessToken.objects.get(token = request.POST.get("access_token"), expires__gt = timezone.now())

        driver = access_token.user.driver

        # Check if Available for Driver Selection
        if Order.objects.filter(driver = driver).exclude(status = Order.ONTHEWAY):
            return JsonResponse({"status": "failed", "error": "Only One Order can be selected at the same time"})

        try:
            order = Order.objects.get(
            id = request.POST["order_id"],
            driver = None,
            status = Order.READY
            )


            order.driver = driver
            order.status = Order.ONTHEWAY
            order.picked_at = timezone.now()
            order.save()

            return JsonResponse({"status": "success"})

        except Order.DoesNotExist:
            return JsonResponse({"status": "failed", "error": "This order has been picked up by another driver"})

def driver_get_latest_order(request):
    access_token = AccessToken.objects.get(token = request.GET.get("access_token"), expires__gt = timezone.now())

    driver = access_token.user.driver
    order = OrderSerializer(
    Order.objects.filter(driver = driver).order_by("picked_at").last()
    ).data

    return JsonResponse({"order": order})

@csrf_exempt
def driver_complete_order(request):
    access_token = AccessToken.objects.get(token = request.POST.get("access_token"), expires__gt = timezone.now())

    driver = access_token.user.driver
    order = Order.objects.get(id = request.POST["order_id"], driver = driver)
    order.status = Order.DELIVERED
    order.save()
    return JsonResponse({"status": "success"})

def driver_get_revenue(request):
    access_token = AccessToken.objects.get(token = request.GET.get("access_token"), expires__gt = timezone.now())

    driver = access_token.user.driver


    from datetime import timedelta

    revenue = {}
    today = timezone.now()
    current_weekdays = [today + timedelta(days = i) for i in range(0 - today.weekday(), 7 - today.weekday())]

    for day in current_weekdays:
        orders = Order.objects.filter(
            driver = driver,
            status = Order.DELIVERED,
            created_at__year = day.year,
            created_at__month = day.month,
            created_at__day = day.day
        )

        revenue[day.strftime("%a")] = sum(order.total for order in orders)

    return JsonResponse({"revenue": revenue})



@csrf_exempt
def driver_update_location(request):
    if request.method == "POST":
        access_token = AccessToken.objects.get(token = request.POST.get("access_token"), expires__gt = timezone.now())

        driver = access_token.user.driver

        #Set Location String
        driver.location = request.POST["location"]
        driver.save()

        return JsonResponse({"status": "success"})

def get_open_restaurants_near_customer(request):
    '''
    Returns a list of 10 restaurants which are open and near the user
    Latitude and longitude of the customer are required.
    If the starting id of the restaurant is provided, results are filtered 
    on restaurants having id more than that of the provided id
    :param request: http request
    :return: list of restaurants, each entry a dict of the restaurant's attributes
    '''
    from haversine import haversine
    latitude = float(request.GET.get('latitude'))
    longitude = float(request.GET.get('longitude'))
    starting_id = request.GET.get('starting_id')
    batch_size = int(request.GET.get('batch_size', 10))
    operating_distance = int(request.GET.get('distance', 5))
    if starting_id:
        restaurants = Restaurant.objects.filter(id__gt=starting_id).order_by('id')
    else:
        restaurants = Restaurant.objects.all().order_by('id')

    restaurants_within_distance = []
    for restaurant in restaurants:
        distance = None
        if restaurant.latitude and restaurant.longitude:
            distance = haversine((latitude, longitude), (restaurant.latitude, restaurant.longitude))
        if distance and distance <= operating_distance and restaurant.is_open():
            restaurants_within_distance.append(restaurant)
        if len(restaurants_within_distance) >= batch_size:
            break

    serialized_restaurants = RestaurantSerializer(
        restaurants_within_distance,
        many=True,
        context={"request": request}
    ).data

    return JsonResponse({"restaurants": serialized_restaurants})

def get_meal_modifiers(request, restaurant_id):
    meals = Meal.objects.filter(restaurant_id=restaurant_id)
    modifiers = defaultdict(list)
    for meal in meals:
        meal_modifiers = meal.modifier.all()
        for meal_modifier in meal_modifiers:
            modifiers[meal_modifier].append(meal)
    meal_extras = dict()
    for modifier in modifiers.keys():
        meal_extras[modifier.name] = MealSerializer(modifiers[modifier], many=True, context={'request': request}).data

    return JsonResponse({"modifiers": meal_extras})

def get_oldest_order(request):
    '''
    Returns the oldest order which is awaiting a driver in a vicinity of 5km
    requires the latitude and longitude of the driver to determine the business
    :param request: request object of Django
    :return: Order details of the oldest order available
    '''

    latitude = request.GET.get('latitude')
    longitude = request.GET.get('longitude')

    # return error if latitude and longitude are not provided
    if not (latitude and longitude):
        return JsonResponse({
            'status': 'failed',
            'error': 'Driver co-ordinates required'
        })

    # convert to float
    latitude = float(latitude)
    longitude = float(longitude)

    # cycle through orders which are ready sorted by order created on time
    # return first order which is in the vicinity of the driver
    open_orders = Order.objects.filter(status=Order.READY).order_by('created_at')
    for order in open_orders:
        if order.restaurant.get_distance(latitude, longitude) <= 5:
            return JsonResponse({'order': OrderSerializer(order).data})

    return JsonResponse({
        "status": "success",
        "message": "No orders are ready in your vicinity"
    })
