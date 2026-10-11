from django.urls import NoReverseMatch, reverse


def user_theme_settings(request):
    """Сохраняем имя процессора, зарегистрированного в настройках сайта."""
    context = {'use_studio_design': request.user.is_authenticated}
    try:
        context['meropriyatie_list_url'] = reverse('meropriyatie_list')
    except NoReverseMatch:
        context['meropriyatie_list_url'] = None
    return context
