from flask import Flask, render_template, jsonify, request, send_from_directory, redirect, url_for, session
import json
import os
import uuid

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', str(uuid.uuid4()))  # Add a secret key for session management

class GameState:
    def __init__(self, json_file='books_network.json'):
        with open(json_file, 'r') as file:
            self.books = json.load(file)['books']
        
        self.current_book_index = 0
        self.total_books = len(self.books)
        self.revealed_characters = []
        self.score = 100
        self.game_over = False

    @property
    def current_book(self):
        return self.books[self.current_book_index]
    
    def get_graph_data(self):
        """Return graph data in a format suitable for vis-network visualization."""
        visible_nodes = [
            {
                "id": n["id"],
                "label": n["id"],
                "count": n["count"],
                "type": n["type"]
            }
            for n in self.current_book['nodes'] 
            if n['id'] in self.revealed_characters
        ]
        
        visible_edges = [
            {
                "source": e["source"],
                "target": e["target"],
                "weight": e["weight"]
            }
            for e in self.current_book['edges']
            if e['source'] in self.revealed_characters 
            and e['target'] in self.revealed_characters
        ]
        
        return {
            "nodes": visible_nodes,
            "links": visible_edges
        }
    
    def reveal_next_character(self):
        if len(self.revealed_characters) < len(self.current_book['nodes']):
            next_char = self.current_book['nodes'][len(self.revealed_characters)]
            self.revealed_characters.append(next_char['id'])
            # Only reduce score if this isn't the first character
            if len(self.revealed_characters) > 1:
                self.score = max(0, self.score - 10)
            return True
        return False
    
    def check_guess(self, guess):
        book_title = self.current_book['title']
        # Add space before capitals in the book title for better user experience
        formatted_title = ''.join([' '+c if c.isupper() and i > 0 else c for i, c in enumerate(book_title)])
        formatted_title = formatted_title.strip()
        
        # Normalize both strings for comparison
        normalized_guess = guess.lower().replace(" ", "").replace("-", "")
        normalized_title = formatted_title.lower().replace(" ", "").replace("-", "")
        
        return normalized_guess == normalized_title
    
    def next_book(self, skip=False):
        if skip:
            self.score = 0
        
        if self.current_book_index < self.total_books - 1:
            self.current_book_index += 1
            self.revealed_characters = []
            self.score = 100
            self.game_over = False
            return True
        else:
            self.game_over = True
            return False

# Use a global game state for simplicity, but track reset status in session
game_state = GameState('books_network.json')

# Helper function to ensure the game state is properly initialized
def ensure_game_state():
    global game_state
    
    # Check if we need to reset based on session token
    if 'reset_needed' in session and session['reset_needed']:
        game_state = GameState('books_network.json')
        session['reset_needed'] = False
        
    # Also reset if this is a new session
    if 'game_initialized' not in session:
        game_state = GameState('books_network.json')
        session['game_initialized'] = True
    
    return game_state

@app.route('/')
def index():
    # Mark that reset is needed on next page load
    session['reset_needed'] = True
    
    # Ensure game state is initialized
    gs = ensure_game_state()
    
    # Reveal first character if it's a fresh game
    if not gs.revealed_characters:
        gs.reveal_next_character()
        
    return render_template('index.html')

@app.route('/instructions')
def instructions():
    # Mark that reset is needed on next page load
    session['reset_needed'] = True
    return render_template('instructions.html')

@app.route('/js/<path:path>')
def send_js(path):
    return send_from_directory('static/js', path)

@app.route('/css/<path:path>')
def send_css(path):
    return send_from_directory('static/css', path)

@app.route('/reveal', methods=['POST'])
def reveal():
    gs = ensure_game_state()
    
    if gs.reveal_next_character():
        graph_data = gs.get_graph_data()
        return jsonify({
            'graph': graph_data,
            'characters': gs.revealed_characters,
            'score': gs.score,
            'gameOver': len(gs.revealed_characters) == len(gs.current_book['nodes']),
            'currentBook': gs.current_book_index + 1,
            'totalBooks': gs.total_books
        })
    return jsonify({'gameOver': True})

@app.route('/guess', methods=['POST'])
def guess():
    gs = ensure_game_state()
    
    guess = request.json.get('guess', '')
    is_correct = gs.check_guess(guess)
    
    response_data = {
        'correct': is_correct,
        'score': gs.score,
        'currentBook': gs.current_book_index + 1,
        'totalBooks': gs.total_books
    }
    
    if is_correct:
        has_next_book = gs.next_book()
        if has_next_book:
            # Reveal first character of next book automatically
            gs.reveal_next_character()
            graph_data = gs.get_graph_data()
            response_data.update({
                'nextBook': True,
                'graph': graph_data
            })
        else:
            response_data['gameComplete'] = True
    else:
        gs.score = max(0, gs.score - 10)
        response_data['score'] = gs.score
    
    return jsonify(response_data)

@app.route('/skip', methods=['POST'])
def skip():
    gs = ensure_game_state()
    
    has_next_book = gs.next_book(skip=True)
    if has_next_book:
        # Reveal first character of next book automatically
        gs.reveal_next_character()
        graph_data = gs.get_graph_data()
        return jsonify({
            'nextBook': True,
            'currentBook': gs.current_book_index + 1,
            'totalBooks': gs.total_books,
            'score': 0,
            'graph': graph_data
        })
    return jsonify({
        'gameComplete': True,
        'score': 0
    })

@app.route('/reset', methods=['POST'])
def reset():
    global game_state
    game_state = GameState('books_network.json')
    # Reveal first character automatically
    game_state.reveal_next_character()
    graph_data = game_state.get_graph_data()
    
    # Clear the need for reset
    session['reset_needed'] = False
    session['game_initialized'] = True
    
    return jsonify({
        'success': True,
        'graph': graph_data,
        'score': 100,
        'currentBook': 1,
        'totalBooks': game_state.total_books
    })

# Simple API endpoint to check if we need to reset
@app.route('/check-reset', methods=['GET'])
def check_reset():
    return jsonify({
        'resetNeeded': session.get('reset_needed', True)
    })

if __name__ == '__main__':
    app.run(debug=True)
