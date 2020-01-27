from django.http import Http404
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views import generic
from django.contrib.auth import mixins

from requests import HTTPError

from .forms import SignUpForm
from .helpers import igdb_api, twitter_api


class IndexView(generic.ListView):
    template_name = 'gamecatalog/home.html'
    context_object_name = 'games'

    def __init__(self):
        super().__init__()

        self.current_page = 1

        self.search_query = ''

        self.rating_from = None
        self.rating_to = None

        self.platforms = igdb_api.IGDB_API.get_all_resources_at_url(
            igdb_api.IGDB_API.PLATFORMS_URL,
            igdb_api.IGDB_API.PLATFORMS_SLUG_COLUMN_NAME)

        self.checked_platforms_ids = None

        self.genres = igdb_api.IGDB_API.get_all_resources_at_url(
            igdb_api.IGDB_API.GENRES_URL,
            igdb_api.IGDB_API.GENRES_COLUMN_NAME)

        self.checked_genres_ids = None

        self.filter_params = ''

    def dispatch(self, request, *args, **kwargs):

        try:
            if 'page' in self.request.GET:
                self.current_page = int(self.request.GET['page'])
        except ValueError:
            raise Http404()

        if not (1 <= self.current_page <= 3):
            raise Http404()

        if 'search' in self.request.GET:
            self.search_query = self.request.GET['search']

            self.filter_params += f'&search={self.search_query}'

        if 'rating_from' in self.request.GET:
            self.rating_from = int(self.request.GET['rating_from'])

            self.filter_params += f'&rating_from={self.rating_from}'

        if 'rating_to' in self.request.GET:
            self.rating_to = int(self.request.GET['rating_to'])

            self.filter_params += f'&rating_to={self.rating_to}'

        self.checked_platforms_ids = self.__handle_get_filter_params(
            self.platforms, igdb_api.IGDB_API.PLATFORMS_SLUG_COLUMN_NAME)

        self.checked_genres_ids = self.__handle_get_filter_params(
            self.genres, igdb_api.IGDB_API.GENRES_COLUMN_NAME)

        return super().dispatch(request, args, kwargs)

    def __handle_get_filter_params(self, possible_params, name_key):
        params = set()
        for get_param in self.request.GET:
            for possible_param in possible_params:
                if possible_param[name_key] == get_param:
                    params.add(possible_param['id'])

                    self.filter_params += f'&{get_param}=on'

        return params

    def get_queryset(self):
        games = igdb_api.IGDB_API.get_all_games(
            games_count=18,
            search_query=(self.search_query
                          if self.search_query != '' else None),
            user_rating_range=(self.rating_from, self.rating_to),
            platform_ids=self.checked_platforms_ids,
            genre_ids=self.checked_genres_ids)

        return games[(self.current_page - 1) * 6:
                     (self.current_page - 1) * 6 + 6]

    def get_context_data(self, **kwargs):
        context = super(IndexView, self).get_context_data(**kwargs)

        context['current_page'] = self.current_page

        context['search_query'] = self.search_query

        if self.rating_from is not None:
            context['rating_from'] = self.rating_from

        if self.rating_to is not None:
            context['rating_to'] = self.rating_to

        context['platforms'] = self.platforms
        context['checked_platforms_ids'] = self.checked_platforms_ids

        context['genres'] = self.genres
        context['checked_genres_ids'] = self.checked_genres_ids

        context['filter_params'] = self.filter_params

        return context


class DetailsView(generic.TemplateView):
    template_name = 'gamecatalog/details.html'

    def __init__(self):
        super().__init__()

        self.game = {}
        self.tweets = []

    def dispatch(self, request, *args, **kwargs):
        try:
            self.game = igdb_api.IGDB_API.get_game(kwargs['game_id'])

        except igdb_api.InvalidGameIDError:
            raise Http404()

        try:
            self.tweets = twitter_api.TWITTER_API.get_tweets_for_game(
                self.game['name'])
        except HTTPError:
            pass

        return super().dispatch(request, args, kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['game'] = self.game
        context['tweets'] = self.tweets

        return context


class SignUpView(generic.edit.CreateView):
    form_class = SignUpForm
    success_url = reverse_lazy('gamecatalog:login')
    template_name = 'gamecatalog/sign_up.html'


class ProfileView(mixins.LoginRequiredMixin, generic.TemplateView):
    template_name = 'gamecatalog/profile.html'
