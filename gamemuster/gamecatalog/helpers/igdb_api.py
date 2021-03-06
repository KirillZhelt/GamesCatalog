import requests

from django.conf import settings

from datetime import datetime


def list_values_comma_separated(values):
    return str(values)[1:-1]


class InvalidGameIDError(Exception):
    pass


class InvalidCoverIDError(Exception):
    pass


if not settings.configured:
    settings.configure()


# noinspection PyPep8Naming
class IGDB_API:
    BASE_URL = 'https://api-v3.igdb.com/'

    GAMES_URL = f'{BASE_URL}games'
    COVERS_URL = f'{BASE_URL}covers'
    KEYWORDS_URL = f'{BASE_URL}keywords'
    GENRES_URL = f'{BASE_URL}genres'
    PLATFORMS_URL = f'{BASE_URL}platforms'
    RELEASE_DATES_URL = f'{BASE_URL}release_dates'
    SCREENSHOTS_URL = f'{BASE_URL}screenshots'

    KEYWORDS_COLUMN_NAME = 'slug'
    GENRES_COLUMN_NAME = 'slug'
    PLATFORMS_COLUMN_NAME = 'name'
    PLATFORMS_SLUG_COLUMN_NAME = 'slug'
    RELEASE_DATES_COLUMN_NAME = 'human'
    SCREENSHOTS_COLUMN_NAME = 'url'

    HEADERS = {'user-key': settings.IGDB_API_KEY}

    MAX_GENRES_FOR_GAME_IN_LIST = 2
    MAX_KEYWORDS_FOR_GAME_IN_LIST = 2

    MAX_GENRES_FOR_GAME = 3
    MAX_KEYWORDS_FOR_GAME = 3

    @classmethod
    def __make_request(cls, url, data):
        r = requests.post(url, headers=cls.HEADERS, data=data)

        if r.status_code != 200:
            r.raise_for_status()

        return r.json()

    @classmethod
    def __validate_filters(cls, platform_ids, genre_ids, user_rating_range):
        if (not platform_ids or (platform_ids and not len(platform_ids))) \
                and (not genre_ids or (genre_ids and not len(genre_ids))) \
                and (not user_rating_range
                     or (user_rating_range and len(user_rating_range) != 2)
                     or (user_rating_range and len(user_rating_range) == 2
                         and user_rating_range[0] is None
                         and user_rating_range[1] is None)):
            return False

        return True

    @classmethod
    def __build_filters(cls, platform_ids, genre_ids, user_rating_range):

        if not cls.__validate_filters(platform_ids, genre_ids,
                                      user_rating_range):
            return ''

        conditions = []

        if platform_ids and len(platform_ids):
            conditions.append(
                f'platforms = ({list_values_comma_separated(platform_ids)})')

        if genre_ids and len(genre_ids):
            conditions.append(
                f'genres = ({list_values_comma_separated(genre_ids)})')

        if user_rating_range and len(user_rating_range) == 2 \
                and user_rating_range[0] is not None \
                and user_rating_range[1] is not None:
            lo = user_rating_range[0] * 10
            hi = user_rating_range[1] * 10

            conditions.append(f'rating > {lo} & rating < {hi}')

        filters = 'where ' + conditions[0]

        for i in range(1, len(conditions)):
            filters += f' & {conditions[i]}'

        return filters + ';'

    @classmethod
    def __build_search_query(cls, search_query):
        if search_query:
            return f'search "{search_query}";'

        return 'sort popularity desc;'

    @classmethod
    def __load_specific_data_for_games(cls, games_info):
        # Load cover, genres, keywords from their ids

        cover_ids = tuple((game_info['cover'] for game_info in games_info
                           if 'cover' in game_info))

        if cover_ids:
            covers_for_games = cls.get_covers(cover_ids)

        genre_ids = set()
        for game_info in games_info:
            genre_ids_for_game = game_info.get('genres')

            if genre_ids_for_game is not None:
                genre_ids_for_game = \
                    genre_ids_for_game[0:min(len(genre_ids_for_game),
                                             cls.MAX_GENRES_FOR_GAME_IN_LIST)]

                game_info['genres'] = genre_ids_for_game

                genre_ids.update(genre_ids_for_game)

        if genre_ids:
            genres = cls.get_resources_at_url(cls.GENRES_URL,
                                              cls.GENRES_COLUMN_NAME,
                                              genre_ids)

        keyword_ids = set()
        for game_info in games_info:
            keyword_ids_for_game = game_info.get('keywords')

            if keyword_ids_for_game is not None:
                keyword_ids_for_game = \
                    keyword_ids_for_game[0:
                                         min(len(keyword_ids_for_game),
                                             cls.MAX_KEYWORDS_FOR_GAME_IN_LIST)
                                         ]

                game_info['keywords'] = keyword_ids_for_game

                keyword_ids.update(keyword_ids_for_game)

        if keyword_ids:
            keywords = cls.get_resources_at_url(cls.KEYWORDS_URL,
                                                cls.KEYWORDS_COLUMN_NAME,
                                                keyword_ids)

        for game_info in games_info:
            if game_info['id'] in covers_for_games:
                game_info['cover'] = covers_for_games[game_info['id']]

            genre_ids_for_game = game_info.get('genres')

            if genre_ids_for_game is not None:
                for i, genre_id in enumerate(genre_ids_for_game):
                    genre_ids_for_game[i] = genres[genre_id]

            keyword_ids_for_game = game_info.get('keywords')

            if keyword_ids_for_game is not None:
                for i, keyword_id in enumerate(keyword_ids_for_game):
                    keyword_ids_for_game[i] = keywords[keyword_id]

    @classmethod
    def get_all_games(cls, games_count=10, platform_ids=None, genre_ids=None,
                      user_rating_range=None, search_query=None):
        # Use args to filter games

        games_info = cls.__make_request(cls.GAMES_URL, f'fields name,cover,'
                                                       f'genres,keywords; '
                                                       f'limit '
                                                       f'{games_count}; ' +
                                        cls.__build_filters(platform_ids,
                                                            genre_ids,
                                                            user_rating_range)
                                        +
                                        cls.__build_search_query(search_query))

        cls.__load_specific_data_for_games(games_info)

        return games_info

    @classmethod
    def get_games_by_ids(cls, game_ids):
        if not game_ids:
            return None

        games_info = cls.__make_request(cls.GAMES_URL, f'fields name, cover, genres, keywords; '
                                                       f'where id=({str(game_ids)[1:-1]});'
                                                       f'limit {len(game_ids)};')

        cls.__load_specific_data_for_games(games_info)

        return games_info

    @classmethod
    def __map_ids_to_names(cls, ids, url, column_name):
        if ids:
            genres = cls.get_resources_at_url(url, column_name, ids)

            for i, genre_id in enumerate(ids):
                ids[i] = genres[genre_id]

    @classmethod
    def get_game(cls, game_id):

        game_info = \
            cls.__make_request(cls.GAMES_URL, 'fields name, '
                                              'platforms, keywords, '
                                              'genres, summary, '
                                              'first_release_date, '
                                              'screenshots, rating, '
                                              'rating_count, '
                                              'aggregated_rating, '
                                              'aggregated_rating_count;'
                                              f'where id = {game_id};')

        if len(game_info) == 0:
            raise InvalidGameIDError()

        game_info = game_info[0]

        genre_ids = game_info.get('genres')

        if genre_ids:
            del genre_ids[min(len(genre_ids), cls.MAX_GENRES_FOR_GAME):]
        cls.__map_ids_to_names(genre_ids, cls.GENRES_URL,
                               cls.GENRES_COLUMN_NAME)

        keyword_ids = game_info.get('keywords')

        if keyword_ids:
            del keyword_ids[min(len(keyword_ids), cls.MAX_KEYWORDS_FOR_GAME):]
        cls.__map_ids_to_names(keyword_ids, cls.KEYWORDS_URL,
                               cls.KEYWORDS_COLUMN_NAME)

        screenshots_ids = game_info.get('screenshots')
        cls.__map_ids_to_names(screenshots_ids, cls.SCREENSHOTS_URL,
                               cls.SCREENSHOTS_COLUMN_NAME)

        platform_ids = game_info.get('platforms')
        cls.__map_ids_to_names(platform_ids, cls.PLATFORMS_URL,
                               cls.PLATFORMS_COLUMN_NAME)

        if screenshots_ids:
            game_info['screenshots'] = list(map(lambda s: s[2:],
                                                screenshots_ids))

        if 'rating' in game_info:
            game_info['rating'] = round(game_info['rating'] / 10, 2)

        if 'aggregated_rating' in game_info:
            game_info['aggregated_rating'] = \
                round(game_info['aggregated_rating'] / 10, 2)

        release_date_timestamp = game_info.get('first_release_date')
        if release_date_timestamp:
            game_info['first_release_date'] = datetime.utcfromtimestamp(release_date_timestamp)

        return game_info

    @classmethod
    def get_covers(cls, cover_ids):

        # Because of tuple string representation
        if len(cover_ids) == 1:
            data = f'fields game,url; where id = ({cover_ids[0]});'
        else:
            data = f'fields game,url; where id = {cover_ids};'

        data += f'limit {len(cover_ids)};'

        covers_info = cls.__make_request(cls.COVERS_URL, data)

        if not len(covers_info):
            raise InvalidCoverIDError()

        return {cover_info['game']: cover_info['url'][2:]
                for cover_info in covers_info}

    @classmethod
    def get_resources_at_url(cls, url, column_name, ids):
        # Used to load keywords and genres and other resources by their ids
        # with the specified column_name

        resources_info = \
            cls.__make_request(url, f'fields {column_name}; '
                                    f'where id = ({str(ids)[1:-1]}); '
                                    f'limit {len(ids)};')

        return {resource_info['id']: resource_info[column_name]
                for resource_info in resources_info}

    @classmethod
    def get_all_resources_at_url(cls, url, column_name, *args, resources_count=None):
        query = f'fields id, {column_name}'

        for arg in args:
            query += f', {arg}'

        if not resources_count:
            resources_count = 20

        query += f'; limit {resources_count};'
        return cls.__make_request(url, query)


if __name__ == "__main__":
    games = IGDB_API.get_all_games(games_count=18, search_query="Fifa")
    print(games)

    most_popular_game = games[0]

    print(IGDB_API.get_all_resources_at_url(IGDB_API.GENRES_URL,
                                            IGDB_API.GENRES_COLUMN_NAME))
    print(IGDB_API.get_all_resources_at_url(IGDB_API.PLATFORMS_URL,
                                            IGDB_API.PLATFORMS_COLUMN_NAME))

    print(IGDB_API.get_game(9912))

    print()
    print(IGDB_API.get_game(113344))
