"""Game routing and launcher controllers with legacy URL compatibility."""
from flask import Blueprint, render_template

games_bp = Blueprint('games_catalog', __name__)

# Game template registry mapping: route_path -> (template_path, endpoint_name)
GAME_REGISTRY = {
    # 2048
    '/2048': ('Games/2048/2048.html', 'updown'),
    # Candy Crush
    '/Candy_Crush': ('Games/Candy Crush/Candy_Crush.html', 'Candy_Crush'),
    # Crossword
    '/Crossword': ('Games/Cross word/Crossword.html', 'crossword'),
    '/crossword2ndpage': ('Games/Cross word/crossword2ndpage.html', 'crossword2ndpage'),
    '/animal': ('Games/Cross word/crossword animal.html', 'animal'),
    '/anime': ('Games/Cross word/crossword anime.html', 'anime'),
    '/cities': ('Games/Cross word/crossword cities.html', 'cities'),
    '/movie': ('Games/Cross word/crossword movie.html', 'movie'),
    '/sport': ('Games/Cross word/crossword sport.html', 'sport'),
    '/state': ('Games/Cross word/crossword state.html', 'state'),
    # Flappy Bird
    '/FlappyBird': ('Games/Flappy Birds/flappybird.html', 'flappybird'),
    # Maze
    '/Maze': ('Games/maze/maze.html', 'maze'),
    '/maze2ndpage': ('Games/maze/maze2ndpage.html', 'maze2ndpage'),
    '/mazeeasy': ('Games/maze/mazeeasy.html', 'mazeeasy'),
    '/mazehard': ('Games/maze/mazehard.html', 'mazehard'),
    '/mazemedium': ('Games/maze/mazemedium.html', 'mazemedium'),
    '/mazeveasy': ('Games/maze/mazeveasy.html', 'mazeveasy'),
    # Memory Match
    '/memorymatch': ('Games/MemoryMatch/memorymatch.html', 'memorymatch'),
    '/memorymatch2nd': ('Games/MemoryMatch/memorymatch2nd.html', 'memorymatch2nd'),
    '/matchingeasy': ('Games/MemoryMatch/matchingeasy.html', 'matchingeasy'),
    '/matchingmedium': ('Games/MemoryMatch/matchingmedium.html', 'matchingmedium'),
    '/matchinghard': ('Games/MemoryMatch/matchinghard.html', 'matchinghard'),
    '/matchinginsane': ('Games/MemoryMatch/matchinginsane.html', 'matchinginsane'),
    # Pong
    '/pong': ('Games/pong/pong.html', 'pong'),
    '/pongstart': ('Games/pong/pongstart.html', 'pongstart'),
    '/pongeasy': ('Games/pong/pongeasy.html', 'pongeasy'),
    '/pongmedium': ('Games/pong/pongmedium.html', 'pongmedium'),
    '/ponghard': ('Games/pong/ponghard.html', 'ponghard'),
    '/football': ('Games/pong/football.html', 'football'),
    # Quiz
    '/quiz': ('Games/Quiz/quiz.html', 'quiz'),
    '/quiz2ndpage': ('Games/Quiz/quiz2ndpage.html', 'quiz2ndpage'),
    '/aanimal': ('Games/Quiz/animal.html', 'aanimal'),
    '/Cartoon': ('Games/Quiz/Cartoon.html', 'cartoon'),
    '/food': ('Games/Quiz/food.html', 'food'),
    '/gk': ('Games/Quiz/gk.html', 'gk'),
    '/history': ('Games/Quiz/history.html', 'history'),
    '/indiansport': ('Games/Quiz/indiansport.html', 'indiansport'),
    '/movies': ('Games/Quiz/movies.html', 'movies'),
    '/place': ('Games/Quiz/place.html', 'place'),
    '/riddle': ('Games/Quiz/riddle.html', 'riddle'),
    # Relationship
    '/relations': ('Games/Relationship/relations.html', 'relations'),
    '/Relationshipeasy': ('Games/Relationship/Relationshipeasy.html', 'relationshipeasy'),
    '/Relationshiphard': ('Games/Relationship/Relationshiphard.html', 'relationshiphard'),
    # Math Sequence
    '/mathsequence': ('Games/Sequence/mathsequence.html', 'mathsequence'),
    '/mathsequencegame': ('Games/Sequence/mathsequencegame.html', 'mathsequencegame'),
    # Stone Paper Scissors
    '/stonepapersissors': ('Games/Stone Paper Scissors/stonepapersissors.html', 'stonepapersissor'),
    # Tic Tac Toe
    '/tictactoe': ('Games/TicTacToe/tictactoe.html', 'tictactoe'),
    # Tower Block
    '/TowerBlock': ('Games/TowerBlock/TowerBlock.html', 'towerblock'),
    # Tricky
    '/tricky': ('Games/Tricky/tricky.html', 'tricky'),
    '/trickygame': ('Games/Tricky/trickygame.html', 'trickygame'),
    # Whack a Mole
    '/mole': ('Games/wake a mole/mole.html', 'mole'),
    '/mole2nd': ('Games/wake a mole/mole2nd.html', 'mole2nd'),
    '/moleeasy': ('Games/wake a mole/moleeasy.html', 'moleeasy'),
    '/molemedium': ('Games/wake a mole/molemedium.html', 'molemedium'),
    '/molehard': ('Games/wake a mole/molehard.html', 'molehard'),
    # SpeedType Pro
    '/speedtype': ('Games/SpeedType Pro/speedtype.html', 'speedtype'),
    '/speedtypepro': ('Games/SpeedType Pro/speedtype.html', 'speedtypepro'),
}


def create_game_view(template_path):
    """Factory creating view function for rendering a game template."""
    def view():
        return render_template(template_path)
    return view


def register_game_routes(app_or_bp):
    """Register all game routes and their exact endpoint names."""
    for path, (template_path, endpoint_name) in GAME_REGISTRY.items():
        view_func = create_game_view(template_path)
        view_func.__name__ = endpoint_name
        app_or_bp.add_url_rule(path, endpoint=endpoint_name, view_func=view_func)
