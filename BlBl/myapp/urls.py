# urls.py 中删除重复的路由，只保留一个：
from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('login/', views.login, name='login'),
    path('register/', views.register, name='register'),  # 只保留这个路由
    path('index/', views.index, name='index'),
    # path('', views.index, name='index'),
    path('videolist/', views.videolist, name='videolist'),
    path('detail/<int:videoid>', views.detail, name='myapp_videodetail'),
    path('add_wishlist/<int:videoid>/',views.add_wishlist,name='add_wishlist'),
    path('remove_wishlist/<int:videoid>/',views.remove_wishlist,name='remove_wishlist'),
    path('comment/<int:videoid>/',views.comment, name='myhome_comment'),
    path('keshihua/',views.keshihua, name='keshihua'),
    path('keshihua1/',views.keshihua1, name='keshihua1'),
    path('wordcloud/',views.wordcloud, name='wordcloud'),
    # path('get_wordcloud_data/',views.wordcloud_view,name='get_wordcloud_data'),
    path('wordcloud/data/', views.wordcloud_view, name='wordcloud_data'),
    path('video_rec/',views.video_rec, name='video_rec'),
    path('user_view/',views.user_view, name='user_view'),
    path('change_password/', views.change_password_view, name='change_password'),
    path('logout/', views.logout, name='logout'),
    #调试视图推荐
    path('debug_session/', views.debug_session, name='debug_session'),
    path('ai/', views.ai_chat_page, name='ai_chat_page'),
    path('api/ai_chat/', views.ai_chat_api, name='ai_chat_api'),
]