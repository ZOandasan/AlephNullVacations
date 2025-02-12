from django.db.models.aggregates import Avg
from django.shortcuts import render, redirect
from .models import Location, Reaction, Review, Photo
from .forms import ReviewForm
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.db.models import Count, Avg
from django.contrib.auth.decorators import login_required
import math
import uuid
import boto3
import os


# NAVIGATION operations
def signup(request):
    error_message = ''
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('index')
        else:
            error_message = 'Invalid sign up - try again'
    form = UserCreationForm()
    context = {'form': form, 'error_message': error_message}
    return render(request, 'registration/signup.html', context)


def home(request):
    return render(request, 'home.html')


def about(request):
    return render(request, 'about.html')


def location_index(request):
    locations = Location.objects.all()
    for location in locations:
        location.average = Review.objects.filter(
            location_id=location.id).aggregate(Avg('rating'))
    return render(request, 'locations/index.html', {
        'locations': locations
    })


def location_detail(request, location_id):
    location = Location.objects.get(id=location_id)
    review_form = ReviewForm()
    average = Review.objects.filter(
        location_id=location_id).aggregate(Avg('rating'))
    reactions_count = Reaction.objects.filter(review__location_id=location_id)
    reactions_count = reactions_count.values('review', 'icon').annotate(
        total=Count('icon')).order_by('total')
    count_by_review = {}
    for count in reactions_count:
        if not count['review'] in count_by_review:
            count_by_review[count['review']] = {}
        count_by_review[count['review']][count['icon']] = count['total']

    return render(request, 'locations/detail.html', {
        'location': location,
        'review_form': review_form,
        'average': average['rating__avg'],
        'count_by_review': count_by_review
    })

# LOCATION operations


class LocationCreate(LoginRequiredMixin, CreateView):
    model = Location
    fields = ['name', 'country', 'city', 'latitude', 'longitude']

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


class LocationUpdate(LoginRequiredMixin, UpdateView):
    model = Location
    fields = ['name', 'country', 'city', 'latitude', 'longitude']


class LocationDelete(LoginRequiredMixin, DeleteView):
    model = Location
    success_url = '/locations/'

# REVIEW operations

@login_required
def add_review(request, location_id):
    review = Review.objects.filter(
        user=request.user, location_id=location_id).first()
    if review:
        return redirect('detail', location_id=location_id)

    form = ReviewForm(request.POST)
    if form.is_valid():
        new_review = form.save(commit=False)
        new_review.location_id = location_id
        new_review.user = request.user
        new_review.save()
    return redirect('detail', location_id=location_id)


class ReviewUpdate(LoginRequiredMixin, UpdateView):
    model = Review
    fields = ['content', 'rating']

    ### VERIFY USER EDITING IS THE USER WHO MADE THE REVIEW
    def form_valid(self, form):
        edit_review = form.save(commit=False)
        print(edit_review.user)
        if self.request.user.id != edit_review.user.id:
            return redirect('detail', location_id=edit_review.location.id)
        return super().form_valid(form)


    def get_success_url(self):
        obj = self.get_object()
        return reverse('detail', kwargs={'location_id': obj.location.id})


class ReviewDelete(LoginRequiredMixin, DeleteView):
    model = Review
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        if self.object.user.id == request.user.id:
            self.object.delete()
        return redirect('detail', location_id=self.object.location.id)

    def get_success_url(self):
        obj = self.get_object()
        print(obj)
        return reverse('detail', kwargs={'location_id': obj.location.id})


# PHOTO operations
@login_required
def add_photo(request, location_id):
    photo_file = request.FILES.get('photo-file', None)
    if photo_file:
        s3 = boto3.client('s3')
        key = uuid.uuid4().hex[:6] + \
            photo_file.name[photo_file.name.rfind('.'):]
        try:
            bucket = os.environ['S3_BUCKET']
            s3.upload_fileobj(photo_file, bucket, key)
            url = f"{os.environ['S3_BASE_URL']}{bucket}/{key}"
            Photo.objects.create(
                url=url, location_id=location_id, user=request.user)
        except:
            print('An error occurred uploading file to S3')
    return redirect('detail', location_id=location_id)

# REVIEW operations
@login_required
def add_like(request, review_id):
    obj1 = Reaction.objects.filter(
        user=request.user, review_id=review_id, icon='D').first()
    if obj1:
        obj1.delete()

    review = Review.objects.get(id=review_id)
    obj2, created2 = Reaction.objects.get_or_create(
        user=request.user, review_id=review_id, icon='L')
    if not created2:
        obj2.delete()

    return redirect('detail', location_id=review.location.id)

@login_required
def add_dislike(request, review_id):
    obj1 = Reaction.objects.filter(
        user=request.user, review_id=review_id, icon='L').first()
    if obj1:
        obj1.delete()

    review = Review.objects.get(id=review_id)
    obj2, created2 = Reaction.objects.get_or_create(
        user=request.user, review_id=review_id, icon='D')
    if not created2:
        obj2.delete()

    return redirect('detail', location_id=review.location.id)

def reaction_index(request, review_id):
    likes = Reaction.objects.filter(review_id = review_id, icon = 'L')
    dislikes = Reaction.objects.filter(review_id = review_id, icon = 'D')
    return render(request, 'reaction_index.html', {
        'likes': likes,
        'dislikes': dislikes
    })

