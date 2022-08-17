from email import contentmanager
from django.shortcuts import redirect, render
from .models import Post, Review
from comments.models import Comment
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime, timedelta
from django.db.models import Q, Count
from django.core.paginator import Paginator
import json
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .forms import PostForm

# Create your views here.


def home(request):
    query = request.GET.get('query', None)
    dur = request.GET.get('duration', None)
    ctt = request.GET.get('contact', None)

    q = Q()
    if dur == "regular":
        q.add(Q(duration="정기"), q.AND)

    elif dur == "one-time":
        q.add(Q(duration="번개"), q.AND)

    if ctt == "on":
        q.add(Q(contact="온라인"), q.AND)
    elif ctt == "off":
        q.add(Q(contact="오프라인"), q.AND)
    elif ctt == "mix":
        q.add(Q(contact="혼합"), q.AND)

    if query:
        q.add(Q(title__contains=query), q.OR)
        q.add(Q(tag__contains=query), q.OR)
        q.add(Q(content__contains=query), q.OR)
        q.add(Q(location__contains=query), q.OR)
        q.add(Q(user__nickname__contains=query), q.OR)

    posts = Post.objects.filter(q)

    sort = request.GET.get('sort', 'None')
    if sort == "latest":
        posts = posts.order_by("-published_at")
    elif sort == "views":
        posts = posts.order_by("-views")
    elif sort == "comments":
        posts = posts.annotate(comment_count=Count(
            'comment')).order_by("-comment_count")

    context = {
        "posts": posts,
        "sort": sort,
        "duration": dur,
        "contact": ctt,
    }
    return render(request, template_name="posts/main.html", context=context)


@login_required
def write(request):
    if request.method == "POST":
        form = PostForm(request.POST)
        if form.is_valid():
            if form.cleaned_data["number"] <= 1:
                messages.error(request, "인원 수는 2명 이상!")
                redirect(f"/post/write")
            post = form.save(commit=False)
            post.user = request.user
            post.save()
            return redirect(f"/post/detail/{id}")
        else:
            return redirect("/post/write")

    form = PostForm()
    context = {
        'form': form,
    }

    return render(request, template_name="posts/main_write.html", context=context)


def detail(request, id):
    post = Post.objects.get(id=id)

    all_reviews = post.review_set.all()
    paginator = Paginator(all_reviews, 5)
    page = request.GET.get('page', 1)
    reviews = paginator.get_page(page)

    all_comments = post.comment_set.all().filter(cmt_class=Comment.CMT_PARENT)

    tomorrow = datetime.now() + timedelta(days=1)
    tomorrow = datetime.replace(tomorrow, hour=0, minute=0, second=0)
    expires = datetime.strftime(tomorrow, "%a, %d-%b-%Y %H:%M:%S GMT")

    reviews_len = len(post.review_set.all())
    comments_len = len(post.comment_set.all())
    cur_user = request.user

    if post.user == request.user:  # 현재 로그인한 유저가 해당 모집글을 쓴 유저이면 can_revise가 True
        can_revise = True
    elif not cur_user.is_authenticated:
        can_revise = False
    else:
        can_revise = False
        context = {
            "post": post,
            'can_revise': can_revise,   # can_revise가 True면 수정, 삭제, 모집 완료로 전환 가능
            "reviews": reviews,
            "review_len": reviews_len,
            "comments": all_comments,
            "comments_len": comments_len,
        }

        session_cookie = id
        cookie_name = F'post_views:{session_cookie}'
        response = render(
            request, template_name="posts/main_detail.html", context=context)
        if request.COOKIES.get(cookie_name) is not None:
            cookies = request.COOKIES.get(cookie_name)
            cookies_list = cookies.split('|')
            if str(request.user.id) not in cookies_list:
                response.set_cookie(cookie_name, cookies +
                                    f'|{request.user.id}', expires=expires)
                post.views += 1
                post.save()
                return response
        else:
            response.set_cookie(cookie_name, request.user.id, expires=expires)
            post.views += 1
            post.save()
            return response

    context = {
        "post": post,
        'can_revise': can_revise,
        "reviews": reviews,
        "review_len": reviews_len,
        "comments": all_comments,
        "comments_len": comments_len,
    }
    return render(request, template_name="posts/main_detail.html", context=context)


@login_required
def update(request, id):
    post = Post.objects.get(id=id)
    if request.method == "POST":
        form = PostForm(request.POST)
        if form.is_valid():
            post.title = form.cleaned_data["title"]
            post.location = form.cleaned_data["location"]
            post.contact = form.cleaned_data["contacts"]
            if form.cleaned_data["number"] <= 1:
                messages.error(request, "인원 수는 2명 이상!")
                redirect(f"/post/update/{id}")
            post.number = form.cleaned_data["number"]
            post.tag = form.cleaned_data["tag"]
            post.content = form.cleaned_data["content"]
            post.apply_link = form.cleaned_data["apply_link"]
            post.duration = form.cleaned_data["durations"]
            post.save()

            return redirect(f"/post/detail/{id}")

    form = PostForm(instance=post)
    context = {
        "form": form,
        "id": id,
        "post": post,
    }

    return render(request, template_name="posts/main_revise.html", context=context)


def delete(request, id):
    if request.method == "POST":
        Post.objects.filter(id=id).delete()
        return redirect("/post")


def close(request, id):
    if request.method == "POST":
        Post.objects.filter(id=id).update(activation=False)
        return redirect(f"/post/detail/{id}")


def review_home(request):
    all_reviews = Review.objects.all()
    paginator = Paginator(all_reviews, 5)
    page = request.GET.get('page', 1)
    reviews = paginator.get_page(page)
    context = {
        'reviews': reviews,
    }

    return render(request, template_name="reviews/review.html", context=context)


@login_required
def review_write(request, id):
    if request.method == "POST":
        img = request.FILES.get('review_image')
        content = request.POST['review_content']
        user = request.user
        post = Post.objects.get(id=id)
        Review.objects.create(user=user, content=content, post=post, image=img)
        return redirect(f"/post/detail/{id}")


@login_required
def review_revise(request, id):
    revised_review = Review.objects.get(id=id)

    if request.method == "POST":
        revised_review.user = request.user
        revised_review.content = request.POST['review_content']
        revised_review.post = Review.objects.get(id=id).post
        if request.FILES.get("review_image"):
            revised_review.image = request.FILES.get("review_image")
        else:
            revised_review.image = revised_review.image
        revised_review.save()
        return redirect(f"/post/detail/{revised_review.post.id}")

    post = revised_review.post
    all_reviews = post.review_set.all()
    all_comments = post.comment_set.all()

    context = {
        'reviews': all_reviews,
        'revised_review': revised_review,
        'comments': all_comments,
        'post': post
    }
    return render(request, template_name="reviews/review_revise.html", context=context)


def review_delete(request, id):
    if request.method == "POST":
        review = Review.objects.get(id=id)
        post_id = review.post.id
        Review.objects.filter(id=id).delete()
        return redirect(f"/post/detail/{post_id}")
