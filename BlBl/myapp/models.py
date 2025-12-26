from django.db import models
import datetime
from django.db import models
from datetime import datetime

# ... 在你的模型中

from django.db import models
from django.contrib.auth.hashers import make_password
from django.utils import timezone
import datetime

class User(models.Model):
    username = models.CharField(max_length=255, verbose_name='用户名', unique=True)  # 添加唯一约束
    password = models.CharField(max_length=255, verbose_name='密码')
    phone = models.CharField(max_length=11, blank=True, null=True, verbose_name='手机号码')
    face = models.ImageField(
        upload_to='avatars/',
        default='avatars/default.jpg',
        verbose_name='头像',
        blank=True,  # 允许表单为空
        null=True    # 允许数据库为空
    )
    info = models.TextField(blank=True, null=True, verbose_name='个性简介')
    email = models.EmailField(max_length=255, unique=True, verbose_name='邮箱')
    addtime = models.DateTimeField(default=timezone.now, verbose_name='注册时间')  # 使用timezone.now更规范
    is_active = models.BooleanField(default=True, verbose_name='是否激活')  # 添加激活状态字段

    class Meta:
        verbose_name = '用户'
        verbose_name_plural = '用户'
        db_table = 'users'  # 指定数据库表名
        ordering = ['-addtime']  # 按注册时间倒序排列

    def __str__(self):
        return self.username

    def save(self, *args, **kwargs):
        """重写save方法，自动加密密码"""
        # 如果密码未加密（不是以pbkdf2_sha256开头），则加密存储
        if self.password and not self.password.startswith(('pbkdf2_sha256$', 'bcrypt$', 'argon2')):
            self.password = make_password(self.password)
        super().save(*args, **kwargs)





# Create your models here.
class StudyClean(models.Model):
    video_id = models.CharField(max_length=255, verbose_name='视频id')
    video_url = models.URLField(verbose_name='视频地址')
    author = models.CharField(max_length=255, verbose_name='作者')
    video_description = models.TextField(verbose_name='视频文案')
    video_duration = models.CharField(max_length=55, verbose_name='视频时长')
    damaku_count = models.IntegerField(verbose_name='弹幕数量')
    favorites_count = models.IntegerField(verbose_name='收藏人数')
    likes_count = models.IntegerField(verbose_name='点赞人数')
    image_url = models.URLField(verbose_name='图片地址')
    publish_timestamp = models.DateTimeField(verbose_name='发布时间')
    comments_count = models.IntegerField(verbose_name='评论人数')
    tags = models.CharField(max_length=255, verbose_name='标签')
    title = models.CharField(max_length=255, verbose_name='标题')
    video_type = models.CharField(max_length=100, verbose_name='视频类型')
    category = models.CharField(max_length=100, verbose_name='类别')

    class Meta:
        verbose_name = '学习数据'
        verbose_name_plural = '学习数据列表'
        db_table = 'study_clean'

    def __str__(self):
        return self.title
class Comment(models.Model):
    uid = models.IntegerField()
    fid = models.IntegerField()
    realname = models.CharField(max_length=11)
    content = models.TextField()
    ctime = models.DateTimeField(null=True)

class Wishlist(models.Model):
    # 1. user是外键，保留on_delete
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    # 2. video改为外键（关联视频模型，比如你的StudyClean模型）
    video = models.ForeignKey(
        'StudyClean',  # 关联你的视频模型（如果模型在当前文件，直接写StudyClean）
        on_delete=models.CASCADE,  # 外键必须加on_delete
        verbose_name="收藏的视频"
    )
    added_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'video')  # 确保用户不会重复收藏同一视频

    def __str__(self):
        return f"{self.user.username} 收藏了 {self.video.title}"


class Rec(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="用户")
    video = models.ForeignKey(StudyClean, on_delete=models.CASCADE, verbose_name="视频")
    score = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="评分")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        db_table = 'myapp_rec'  # 修改为实际存在的表名
        verbose_name = '推荐记录'
        verbose_name_plural = '推荐记录'