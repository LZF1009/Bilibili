import json
import os
import re
from calendar import month
from functools import wraps

import logger
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from BlBl import settings
from attr.setters import convert
from django.conf import settings
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db import transaction
from django.db.models import Count, Sum, DateField, F  # DateField在这里导入
from django.db.models.functions import Cast  # Cast从functions导入
from django.contrib.auth.hashers import make_password, check_password
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.utils.timezone import now
from unicodedata import category
try:
    from Instruct import generate_chat_reply
except ImportError:
    generate_chat_reply = None
from myapp.models import User, StudyClean, Comment, Wishlist,Rec
from collections import Counter
import numpy
from datetime import datetime, timedelta
TEMPLATE_PATH = 'templates/'


def get_template(template_name):
    template_mapping = {
        'login': 'auth-login.html',
        'register': 'auth-register.html',
        'index': 'index.html',
        'video_list': 'video-list.html',
        'video_detail': 'video-detail.html',
        # 'keshihua': 'keshihua.html',
        #'keshihua1': 'keshihua1.html',
        #'wordcloud': 'wordcloud.html',
        'change_password':'change_password.html',
        'ai_chat': 'ai-chat.html',

    }
    return template_mapping.get(template_name, f'{template_name}.html')

def login_required(view_func):  # 修正函数名拼写（optonel_request → login_required）
    @wraps(view_func)  # 修正参数拼写（viem_func → view_func）
    def wrapper(request, *args, **kwargs):
        user_id = request.session.get('user_id')
        if not user_id:  # 简化逻辑，直接判断用户是否登录
            # 检查是否为AJAX请求
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":  # 修正header拼写（X-requested-with → X-Requested-With）
                return JsonResponse({'error': '请先登录', 'redirect': '/login/'}, status=401)  # 修正redirect拼写
            return redirect('login')  # 未登录且非AJAX请求，重定向到登录页
        return view_func(request, *args, **kwargs)  # 登录后执行原视图
    return wrapper



# 将 optonel_login 修正为 optional_login
def optional_login(view_func):  # 修正函数名和参数拼写
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        user_id = request.session.get('user_id')
        current_user = None
        if user_id:
            try:
                current_user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                request.session.pop('user_id', None)
        request.current_user = current_user
        return view_func(request, *args, **kwargs)  # 修正返回语句缩进
    return wrapper  # 缺少的返回语句，必须添加


def login(request):
    # 如果用户已登录，直接跳转到首页
    if request.session.get('user_id'):
        return redirect('index')  # 或 redirect('/videolist/')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()

        # 空值验证
        if not username or not password:
            return JsonResponse({
                'success': False,
                'error': '用户名和密码不能为空'
            })

        # 查询用户并验证密码
        user = User.objects.filter(username=username).first()
        if user:
            if check_password(password, user.password):
                # 登录成功，设置session
                request.session['user_id'] = user.id
                request.session['username'] = user.username
                request.session.set_expiry(86400)  # 设置session过期时间为1天

                # 返回成功信息和跳转地址
                return JsonResponse({
                    'success': True,
                    'user_id': user.id,
                    'username': user.username,
                    'redirect_url': '/videolist/'  # 指定登录后跳转的页面
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': '密码错误，请重试'
                })
        else:
            return JsonResponse({
                'success': False,
                'error': '用户名不存在，请检查'
            })
    # GET请求返回登录页面
    template = get_template('login')
    return render(request, template)


def register(request):
    if request.method == 'POST':
        try:
            # 1. 获取并清洗前端参数
            username = request.POST.get('username', '').strip()
            email = request.POST.get('email', '').strip()
            password = request.POST.get('password', '').strip()
            confirm_password = request.POST.get('confirmPassword', '').strip()
            agree = request.POST.get('agree')

            # 2. 表单验证
            errors = {}
            if not username:
                errors['username'] = '用户名不能为空'
            if not email:
                errors['email'] = '邮箱不能为空'
            elif not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
                errors['email'] = '邮箱格式不正确'
            if not password:
                errors['password'] = '密码不能为空'
            elif len(password) < 8:
                errors['password'] = '密码长度不能少于8位'
            if password != confirm_password:
                errors['confirmPassword'] = '两次密码不一致'
            if not agree:
                errors['agree'] = '请阅读并同意相关条款'

            # 3. 返回验证错误
            if errors:
                return JsonResponse({"success": False, "errors": errors, "message": "信息有误"})

            # 4. 检查用户名/邮箱唯一性
            if User.objects.filter(username=username).exists():
                return JsonResponse({"success": False, "message": "用户名已被注册"})
            if User.objects.filter(email=email).exists():
                return JsonResponse({"success": False, "message": "该邮箱已绑定账号"})

            # 5. 创建用户（使用正确的字段名）
            User.objects.create(
                username=username,
                email=email,
                password=make_password(password),
                addtime=timezone.now(),  # 确保User模型有addtime字段
                is_active=True
            )

            return JsonResponse({"success": True, "message": "注册成功"})

        except Exception as e:
            print(f"注册异常：{str(e)}")
            return JsonResponse({"success": False, "message": f"注册失败：{str(e)}"})

    template_name = get_template('register')
    return render(request, template_name)

@optional_login
def index(request):
    # 基础统计
    total_user = User.objects.count()
    total_video = StudyClean.objects.count()

    # 视频分类统计
    video_type_stats = list(StudyClean.objects.values('category').annotate(count=Count('id')).order_by('-count'))

    # 点赞、评论、收藏统计（处理None值）
    total_likes = StudyClean.objects.aggregate(total_likes=Sum('likes_count'))['total_likes'] or 0
    total_comments = StudyClean.objects.aggregate(total_comments=Sum('comments_count'))['total_comments'] or 0
    total_favorites = StudyClean.objects.aggregate(total_favorites=Sum('favorites_count'))['total_favorites'] or 0

    # 最新评论
    latest_comments = Comment.objects.order_by('-ctime')[:3]

    # 收藏统计（修复字段名错误）
    wishlist_stats = Wishlist.objects.values(
        'video__id',
        'video__image_url',
        'video__title',
        'video__category',
        'video__video_type',
        'video__likes_count'
    ).annotate(
        collect_count=Count('id'),
        favorites_count=F('video__favorites_count')
    ).order_by('-collect_count')[:10]

    # 用户注册统计（修复字段名和语法）
    user_creation_stats = User.objects.annotate(
        day=Cast('addtime', DateField())  # 确保User模型有addtime字段
    ).values('day').annotate(
        count=Count('id')
    ).order_by('day')

    # 格式化日期（处理None值）
    user_creation_stats = [
        {'day': stat['day'].strftime('%Y-%m-%d') if stat['day'] else '', 'count': stat['count']}
        for stat in user_creation_stats
    ]

    # 组装上下文数据
    user_data = {
        'total_user': total_user,
        'total_video': total_video,
        'total_likes': total_likes,
        'total_comments': total_comments,
        'total_favorites': total_favorites,
        'video_type_stats': video_type_stats,
        'user_creation_stats': user_creation_stats,
    }

    # 获取当前登录用户
    current_user = None
    if 'user_id' in request.session:
        current_user = User.objects.filter(id=request.session['user_id']).first()

    context = {
        'user_data': user_data,
        'latest_comments': latest_comments,
        'wishlist_stats': wishlist_stats,
        'current_user': current_user,

    }

    return render(request, get_template('index'), context)

@optional_login
def videolist(request):
    # 数据查询逻辑（保持不变）
    videolist = StudyClean.objects.all()
    category = StudyClean.objects.values('category').distinct()
    selected_category = request.GET.get('category', 'all')

    if selected_category != 'all':
        videolist = videolist.filter(category=selected_category)

    item_per_page = 20
    paginator = Paginator(videolist, item_per_page)
    page_number = request.GET.get('page', 1)

    try:
        page = int(page_number)
        if page < 1:
            page = 1
    except ValueError:
        page = 1

    try:
        page_obj = paginator.get_page(page)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(paginator.num_pages)

    # 关键修正：直接使用根templates目录下的模板名（无需加应用前缀）
    template_name = get_template('video_list')  # 返回 'video-list.html'
    return render(request, template_name, {
        'page_obj': page_obj,
        'category': category,
        'selected_category': selected_category
    })

@optional_login
def detail(request, videoid):
    videoobj =StudyClean.objects.get(id = videoid)
    # 根据当前视频的category获取相关类型的其他视频，并排除当前查看的视频
    categorys = StudyClean.objects.filter(category=videoobj.category).exclude(id=videoid).order_by('?')[:10]

    videolist = StudyClean.objects.all().exclude(id=videoid)[:3]

    commentlist = Comment.objects.filter(fid=videoid)
    from django.db import connection
    commentlist = Comment.objects.filter(fid=videoid)
    print("查询SQL：", commentlist.query)  # 控制台会显示执行的S
    print("评论数量：", commentlist.count())  # 控制台会显示数据库中fid=1的数量（比如截图中的10+条）
    print("评论数据：", list(commentlist.values()))
    is_wishlist = False

    user_id = request.session.get('user_id')

    if user_id:
        is_wishlist = Wishlist.objects.filter(user_id=user_id,video=videoobj).exists()

    context = {
        'videoinfo': videoobj,
        'videolist': videolist,
        'commentlist': commentlist,
        'categorys': categorys,
        'is_wishlist': is_wishlist,


    }
    return render(request,get_template('video_detail'),context)


def add_wishlist(request,videoid):
    if request.method == 'POST':
        user_id = request.session['user_id']
        user = User.objects.get(id=user_id)

        videoobj = StudyClean.objects.get(id=videoid)
        if not Wishlist.objects.filter(user=user,video=videoobj).exists():
            wishlist_itme = Wishlist(user=user,video=videoobj)
            wishlist_itme.save()
            return JsonResponse({'status': 'success', 'message': '收藏成功'})
    return JsonResponse({'status': 'error','message':'操作失败！'},status=400)




def remove_wishlist(request,videoid):
    if request.method == 'POST':
        user_id = request.session['user_id']
        user = User.objects.get(id=user_id)
        videoobj = StudyClean.objects.get(id=videoid)
        Wishlist.objects.filter(user=user,video=videoobj).delete()
        return JsonResponse({'status': 'success', 'message': '取消收藏成功'})
    return JsonResponse({'status': 'error', 'message': '操作失败！'}, status=400)




import logging
logger = logging.getLogger(__name__)

@optional_login
def comment(request, videoid):
    if request.method == 'POST':
        # 验证用户是否登录
        if 'user_id' not in request.session:
            logger.warning(f"未登录用户尝试评论视频{videoid}")
            return JsonResponse({
                'status': 'error',
                'message': '请先登录'
            }, status=401)

        try:
            uid = request.session['user_id']
            user = User.objects.get(id=uid)
            realname = user.username
            comment_text = request.POST.get('comment', '').strip()

            # 验证评论内容
            if not comment_text:
                logger.warning(f"用户{uid}提交空评论（视频{videoid}）")
                return JsonResponse({
                    'status': 'error',
                    'message': '评论内容不能为空'
                }, status=400)

            # 验证视频ID有效性
            try:
                videoid_int = int(videoid)
            except ValueError:
                logger.error(f"无效的视频ID：{videoid}")
                return JsonResponse({
                    'status': 'error',
                    'message': '视频ID格式错误'
                }, status=400)

            # 使用数据库事务确保数据一致性
            with transaction.atomic():
                # 构造评论数据
                commentobj = Comment.objects.create(
                    uid=uid,
                    fid=videoid_int,
                    realname=realname,
                    content=comment_text,
                    ctime=timezone.now()
                )

            logger.info(f"用户{uid}成功评论视频{videoid_int}（评论ID：{commentobj.id}）")

            # 返回JSON数据（时间格式与模板一致）
            return JsonResponse({
                'status': 'success',
                'realname': realname,
                'comment': comment_text,
                'ctime': commentobj.ctime.strftime("%m-%d %H:%M"),
                'comment_id': commentobj.id  # 返回评论ID，便于前端追踪
            })

        except User.DoesNotExist:
            logger.error(f"用户{uid}不存在")
            return JsonResponse({
                'status': 'error',
                'message': '用户不存在'
            }, status=404)
        except Exception as e:
            logger.error(f"评论失败（视频{videoid}）：{str(e)}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': '评论提交失败，请稍后重试'
            }, status=500)

    # GET请求返回错误
    return JsonResponse({
        'status': 'error',
        'message': '仅支持POST请求'
    }, status=405)


def keshihua(request):
    study_data = StudyClean.objects.all()
    video_types = Counter()
    authors = Counter()

    # 收集视频信息
    video_info = []
    for video in study_data:
        video_types[video.video_type] += 1
        authors[video.author] += 1
        video_info.append({
            'title': video.title,
            'likes': video.likes_count,
            'favorites': video.favorites_count,
            'comments': video.comments_count
        })

    # 处理排序数据
    sorted_video_types = sorted(video_types.items(), key=lambda x: x[1], reverse=True)
    sorted_authors = sorted(authors.items(), key=lambda x: x[1], reverse=True)

    # 点赞排行
    sorted_by_likes = sorted(video_info, key=lambda x: x['likes'], reverse=True)[:10]
    likes_titles = [item['title'] for item in sorted_by_likes]
    likes_values = [item['likes'] for item in sorted_by_likes]

    # 收藏排行
    sorted_by_favorites = sorted(video_info, key=lambda x: x['favorites'], reverse=True)[:10]
    favorites_titles = [item['title'] for item in sorted_by_favorites]
    favorites_values = [item['favorites'] for item in sorted_by_favorites]
    total_authors_count = StudyClean.objects.values('author').distinct().count()

    # views.py 中新增
    # 统计热门视频数（自定义规则：点赞≥1000 且 收藏≥500）
    hot_video_count = 0
    for video in study_data:
        if video.likes_count >= 30000 and video.favorites_count >= 10000:
            hot_video_count += 1

    # 新增：统计活跃作者（半年内发过作品的作者）
    # 计算半年前的时间点
    half_year_ago = timezone.now() - timedelta(days=30)

    # 修改这里：将 'created_at' 替换为 'publish_timestamp'
    active_authors = StudyClean.objects.filter(
        publish_timestamp__gte=half_year_ago  # 关键修改
    ).values('author').distinct()

    # 统计活跃作者数量
    active_author_count = active_authors.count()

    context = {
        'video_types': json.dumps(sorted_video_types),
        'authors': json.dumps(sorted_authors),
        'likes': json.dumps(likes_values),
        'likes_titles': json.dumps(likes_titles),  # 新增
        'favorites': json.dumps(favorites_values),
        'favorites_titles': json.dumps(favorites_titles),  # 新增
        'active_author_count': active_author_count,
        'total_authors_count': total_authors_count,  # 新增的总作者数

        'hot_video_count' :hot_video_count

    }

    return render(request, 'keshihua.html', context)

def convert_duration_to_minutes(duration_str):
    """
    将视频时长字符串转换为分钟
    格式可能是: "1:23:45" 或 "23:45" 或 "45"
    """
    try:
        parts = duration_str.split(':')
        if len(parts) == 3:  # 时:分:秒
            hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
            return hours * 60 + minutes + seconds / 60
        elif len(parts) == 2:  # 分:秒
            minutes, seconds = int(parts[0]), int(parts[1])
            return minutes + seconds / 60
        elif len(parts) == 1:  # 只有秒
            seconds = int(parts[0])
            return seconds / 60
        else:
            return 0
    except (ValueError, AttributeError):
        return 0


def keshihua1(request):
    # 获取筛选参数
    time_range = request.GET.get('timeRange', 'all')  # all, month, halfyear, year
    data_type = request.GET.get('dataType', 'comments')  # comments, likes, favorites, damaku
    video_type = request.GET.get('videoType', 'all')  # 视频类型
    category = request.GET.get('category', 'all')  # 类别

    # 获取所有数据
    study_data = StudyClean.objects.all()

    # 应用时间范围筛选
    if time_range != 'all':
        now = datetime.now()
        if time_range == 'month':
            start_date = now - timedelta(days=30)
        elif time_range == 'halfyear':
            start_date = now - timedelta(days=180)
        elif time_range == 'year':
            start_date = now - timedelta(days=365)
        else:
            start_date = now - timedelta(days=365)  # 默认一年

        study_data = study_data.filter(publish_timestamp__gte=start_date)

    # 应用视频类型筛选
    if video_type != 'all':
        study_data = study_data.filter(video_type=video_type)

    # 应用类别筛选
    if category != 'all':
        study_data = study_data.filter(category=category)

    # 视频时长和各项数据
    video_durations = []
    likes_counts = []
    favorites_counts = []
    damaku_counts = []
    comments_counts = []

    for video in study_data:
        duration_in_minutes = convert_duration_to_minutes(video.video_duration)
        video_durations.append(duration_in_minutes)
        likes_counts.append(video.likes_count)
        favorites_counts.append(video.favorites_count)
        damaku_counts.append(video.damaku_count)
        comments_counts.append(video.comments_count)

    # 根据数据类型选择要展示的数据
    if data_type == 'comments':
        target_counts = comments_counts
    elif data_type == 'likes':
        target_counts = likes_counts
    elif data_type == 'favorites':
        target_counts = favorites_counts
    else:  # damaku
        target_counts = damaku_counts

    # 每月（不算年份）与目标数据
    publish_months = Counter()
    for video in study_data:
        month = video.publish_timestamp.month
        if data_type == 'comments':
            publish_months[month] += video.comments_count
        elif data_type == 'likes':
            publish_months[month] += video.likes_count
        elif data_type == 'favorites':
            publish_months[month] += video.favorites_count
        else:  # damaku
            publish_months[month] += video.damaku_count

    # 视频时长与目标数据
    video_duration_data = list(zip(video_durations, target_counts))

    # 将publish_month_data转换为列表
    publish_month_data = [publish_months.get(month, 0) for month in range(1, 13)]

    # 计算每月视频数量
    video_count_per_month = Counter()
    for video in study_data:
        month = video.publish_timestamp.month
        video_count_per_month[month] += 1

    video_count_data = [video_count_per_month.get(month, 0) for month in range(1, 13)]

    # 获取可筛选的选项
    video_types = StudyClean.objects.values_list('video_type', flat=True).distinct()
    categories = StudyClean.objects.values_list('category', flat=True).distinct()

    # 如果是AJAX请求，返回JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'video_duration_data': video_duration_data,
            'publish_month_data': publish_month_data,
            'video_count_data': video_count_data,
            'data_count': study_data.count()
        })

    # 如果是普通请求，渲染页面
    context = {
        'video_duration_data': json.dumps(video_duration_data),
        'publish_month_data': json.dumps(publish_month_data),
        'video_count_data': json.dumps(video_count_data),
        'data_count': study_data.count(),
        'video_types': list(video_types),
        'categories': list(categories)
    }
    return render(request, 'keshihua1.html', context)


@login_required
def wordcloud(request):
    video_types = StudyClean.objects.values_list('category', flat=True).distinct()
    return render(request, 'wordcloud.html', {'video_types': video_types})


@optional_login
def wordcloud_view(request):
    video_type = request.GET.get('type', '全部')

    if video_type == '全部':
        videos = StudyClean.objects.all()
    else:
        videos = StudyClean.objects.filter(category=video_type)

    # 准备词云数据 - 修复标签处理逻辑
    tags_counter = Counter()
    for video in videos:
        tags = video.tags
        if tags:  # 防止tags字段为None
            # 更健壮的分割方式
            # 1. 替换中文逗号为英文逗号
            # 2. 处理多个连续分隔符
            # 3. 处理换行符等其他分隔符

            # 先统一分隔符
            unified_tags = tags.replace('，', ',')  # 中文逗号转英文逗号
            unified_tags = unified_tags.replace('\n', ',')  # 换行符转逗号
            unified_tags = unified_tags.replace(';', ',')  # 分号转逗号
            unified_tags = unified_tags.replace(' ', ',')  # 空格转逗号（谨慎使用）

            # 分割并清理
            tag_list = [tag.strip() for tag in unified_tags.split(',') if tag.strip()]

            for tag in tag_list:
                tags_counter[tag] += 1

    # 将统计结果转换为列表格式
    data_list = [{'name': tag, 'value': count} for tag, count in tags_counter.items()]

    # 按词频排序（从高到低）
    data_list.sort(key=lambda x: x['value'], reverse=True)

    return JsonResponse({"data": data_list})


@login_required
def video_rec(request):
    """视频推荐视图 - 修复版"""
    try:
        # 方法1：尝试从request.user获取用户ID
        user_id = None

        if request.user.is_authenticated:
            # 正常情况：用户已通过Django认证
            user_id = request.user.id
            print(f"DEBUG: 从request.user获取用户ID: {user_id}")
        else:
            # 备用方案：从session中获取用户ID
            user_id = request.session.get('user_id')
            if user_id:
                print(f"DEBUG: 从session获取用户ID: {user_id}")
                # 尝试创建用户对象（如果不存在）
                try:
                    user = User.objects.get(id=user_id)
                    # 手动设置request.user
                    request.user = user
                except User.DoesNotExist:
                    print(f"WARNING: 用户ID {user_id} 在数据库中不存在")
                    # 创建临时用户对象
                    from django.contrib.auth.models import AnonymousUser
                    request.user = AnonymousUser()
            else:
                print("DEBUG: 未找到用户ID，用户未登录")
                return redirect('login')  # 重定向到登录页面

        if not user_id:
            context = {
                'video_details': [],
                'error': '用户未登录',
                'user_authenticated': False,
            }
            return render(request, 'video_rec.html', context)

        # 获取推荐记录
        recommended_recs = Rec.objects.filter(user_id=user_id).select_related('video')

        print(f"DEBUG: 用户 {user_id} 的推荐记录数量: {recommended_recs.count()}")

        video_details = []
        for rec in recommended_recs:
            if not rec.video:
                continue

            video_details.append({
                'id': rec.video.id,
                'imgurl': rec.video.image_url or '/static/default.jpg',
                'videoname': rec.video.title or '未命名视频',
                'category': rec.video.category or '未分类',
                'recommend': rec.created_at,
                'score': float(rec.score) if rec.score else 0.0,
            })

        # 如果没有推荐记录，使用备用方案
        if not video_details:
            print(f"DEBUG: 用户 {user_id} 没有推荐记录，尝试备用方案")
            video_details = get_fallback_recommendations(user_id)

        context = {
            'video_details': video_details,
            'user_authenticated': True,  # 因为我们有user_id
            'user_id': user_id,
            'username': request.session.get('username', '用户'),
            'debug': settings.DEBUG,
        }

        print(f"DEBUG: 准备渲染模板，视频数量: {len(video_details)}")

    except Exception as e:
        logger.error(f"推荐视图错误: {str(e)}", exc_info=True)
        print(f"ERROR: 推荐视图异常: {e}")

        context = {
            'video_details': [],
            'error': f'系统错误: {str(e)[:100]}',
            'user_authenticated': bool(request.session.get('user_id')),
            'user_id': request.session.get('user_id'),
            'debug': settings.DEBUG,
        }

    return render(request, 'video_rec.html', context)


def get_fallback_recommendations(user_id):
    """备用推荐方案"""
    try:
        from .models import StudyClean
        from django.utils import timezone

        fallback_videos = StudyClean.objects.order_by('?')[:5]

        video_details = []
        for i, video in enumerate(fallback_videos):
            video_details.append({
                'id': video.id,
                'imgurl': video.image_url or '/static/default.jpg',
                'videoname': video.title or '未命名视频',
                'category': video.category or '未分类',
                'recommend': timezone.now(),
                'score': 4.5 - (i * 0.1),
            })

        return video_details
    except Exception as e:
        print(f"备用推荐方案错误: {e}")
        return []



    #调试视图推荐


def debug_session(request):
    """调试会话信息"""
    debug_info = {
        'user': str(request.user),
        'authenticated': request.user.is_authenticated,
        'user_id': request.user.id,
        'session_keys': list(request.session.keys()),
        'session_data': dict(request.session),
    }

    return render(request, 'debug.html', {'debug_info': debug_info})


@login_required
def user_view(request):
    # 从session获取user_id，若不存在则用登录用户的id（更稳妥）
    user_id = request.session.get("user_id") or request.user.id
    user = get_object_or_404(User, id=user_id)

    # POST请求：处理用户信息修改
    if request.method == 'POST':
        # 赋值用户信息
        user.username = request.POST.get('username', user.username)  # 加默认值避免空值
        user.email = request.POST.get('email', user.email)
        user.phone = request.POST.get('phone', user.phone)  # 假设User模型有phone字段

        # 时间处理：兼容空值，确保是datetime类型
        addtime_str = request.POST.get('addtime')
        if addtime_str:
            try:
                # 适配常见的时间格式（根据你的前端传参调整）
                user.addtime = datetime.strptime(addtime_str, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                user.addtime = timezone.now()
        else:
            user.addtime = timezone.now()

        user.info = request.POST.get('info', user.info)  # 假设User模型有info字段

        # 处理头像上传
        avatar = request.FILES.get('avatar')
        if avatar:
            # ========== 新增变量开始 ==========
            # 修复：兼容STATIC_ROOT未配置的情况，避免路径为None
            static_root_path = settings.STATIC_ROOT if hasattr(settings,
                                                               'STATIC_ROOT') and settings.STATIC_ROOT else os.path.join(
                settings.BASE_DIR, 'static')
            # ========== 新增变量结束 ==========

            # 优化：使用Django的static路径方法，避免硬编码
            static_path = os.path.join(static_root_path, 'image')  # 替换原settings.STATIC_ROOT为新增的static_root_path
            os.makedirs(static_path, exist_ok=True)

            # ========== 新增变量开始 ==========
            # 修复：防止avatar.name为None导致路径拼接报错
            safe_avatar_name = avatar.name if avatar.name else f"avatar_{user_id}_{int(timezone.now().timestamp())}"
            # ========== 新增变量结束 ==========

            # 优化：避免文件名重复（可选，根据需求调整）
            filename = f"{user_id}_{safe_avatar_name}"  # 替换原avatar.name为新增的safe_avatar_name
            file_path = os.path.join(static_path, filename)

            # 写入文件
            with open(file_path, 'wb+') as destination:
                for chunk in avatar.chunks():
                    destination.write(chunk)

            # 保存相对路径到数据库（前端可通过/static/image/xxx访问）
            user.face = f'image/{filename}'

        # 保存修改
        user.save()

        # 关键修复：redirect参数是URL名称（urls.py中name），而非模板文件名
        # 若urls.py中该视图的name是'user_view'，则直接redirect('user_view')
        return redirect('user_view')  # 重定向到当前视图（GET请求）

    # GET请求：渲染用户信息页面（必须返回，否则POST外的请求会返回None）
    return render(request, 'user_view.html', {'user': user})


@login_required
def change_password_view(request):
    user_id = request.session.get("user_id")
    user = get_object_or_404(User, id=user_id)
    error_message = None
    success_message = None

    if request.method == 'POST':
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        # 使用 Django 的 check_password 函数验证密码
        if not check_password(current_password, user.password):
            error_message = "当前密码错误"

        # 校验新密码与确认密码是否匹配
        elif new_password != confirm_password:
            error_message = "新密码和确认密码不匹配"

        # 验证新密码是否与当前密码相同
        elif check_password(new_password, user.password):
            error_message = "新密码不能与当前密码相同"

        # 验证新密码长度
        elif len(new_password) < 6:
            error_message = "密码长度至少为6个字符"

        else:
            # 使用 make_password 函数哈希新密码
            user.password = make_password(new_password)
            user.save()

            success_message = "密码修改成功"
            return render(request, 'change_password.html',
                          {'user': user, 'success_message': success_message})

    return render(request, 'change_password.html',
                  {'user': user, 'error_message': error_message})


def logout(request):
    request.session.flush()
    return redirect('index')


@optional_login
def ai_chat_page(request):
    """AI助手页面视图 - 修正模板名称"""
    # 改为使用正确的模板名称
    return render(request, 'ai_chat.html')  # 这里原本可能是 'ai-chat.html'



#@require_http_methods(["POST"])  # 简化前端调用：前端打开页面后，直接post /send_exmpt并在后端获取token
@csrf_exempt
@require_POST
def ai_chat_api(request):
    """AI聊天API接口 - 根据model_client.py文档优化"""
    try:
        # 解析请求数据
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
        history = data.get('history', [])  # 修复语法错误：data.get[] → data.get()
        system_prompt = data.get('system_prompt', '').strip()

        # 参数验证
        if not user_message:
            return JsonResponse({'error': '消息不能为空'}, status=400)

        # 导入并调用AI模型
        from .model_client import generate_chat_reply

        # 根据文档调用模型，支持所有可选参数
        reply = generate_chat_reply(
            user_message=user_message,
            history=history,
            system_prompt=system_prompt,  # ✅ 正确的参数名
            max_tokens=data.get('max_tokens', 1024),
            temperature=data.get('temperature', 0.7)
        )

        # 返回标准化的响应格式
        return JsonResponse({
            'reply': reply,
            'status': 'success',
            'model': 'DeepSeek-V3.1'  # 添加模型信息
        })

    except json.JSONDecodeError:  # 修复异常类引用错误
        return JsonResponse({'error': '无效的JSON数据格式'}, status=400)

    except ImportError as e:
        return JsonResponse({'error': f'模型客户端加载失败: {str(e)}'}, status=500)

    except ValueError as e:
        # 处理API密钥缺失等配置错误
        return JsonResponse({'error': f'配置错误: {str(e)}'}, status=400)

    except Exception as e:
        # 记录详细错误日志
        logger.error(f"AI聊天API异常: {str(e)}", exc_info=True)  # 修复语法错误：括号不匹配

        return JsonResponse({
            'error': '服务暂时不可用，请稍后重试',
            'detail': str(e)  # 开发环境显示详细错误
        }, status=500)