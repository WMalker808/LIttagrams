#!/Users/max_walker/LittagramVisuals/bin/python3
#!/usr/bin/env python3
from flask import Flask, render_template, jsonify, request, send_from_directory
import json
import os

app = Flask(__name__)

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
                "count": n["count"],  # Changed from 'val' to 'count' to match JS expectations
                "type": n["type"]     # Include type for grouping in JS
            }
            for n in self.current_book['nodes'] 
            if n['id'] in self.revealed_characters
        ]
        
        visible_edges = [
            {
                "source": e["source"],
                "target": e["target"],
                "weight": e["weight"]  # Changed from 'value' to 'weight' to match JSON data
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

game_state = GameState('books_network.json')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/instructions')
def instructions():
    return render_template('instructions.html')

@app.route('/js/<path:path>')
def send_js(path):
    return send_from_directory('static/js', path)

@app.route('/css/<path:path>')
def send_css(path):
    return send_from_directory('static/css', path)

@app.route('/reveal', methods=['POST'])
def reveal():
    if game_state.reveal_next_character():
        graph_data = game_state.get_graph_data()
        return jsonify({
            'graph': graph_data,
            'characters': game_state.revealed_characters,
            'score': game_state.score,
            'gameOver': len(game_state.revealed_characters) == len(game_state.current_book['nodes']),
            'currentBook': game_state.current_book_index + 1,
            'totalBooks': game_state.total_books
        })
    return jsonify({'gameOver': True})

@app.route('/guess', methods=['POST'])
def guess():
    guess = request.json.get('guess', '')
    is_correct = game_state.check_guess(guess)
    
    response_data = {
        'correct': is_correct,
        'score': game_state.score,
        'currentBook': game_state.current_book_index + 1,
        'totalBooks': game_state.total_books
    }
    
    if is_correct:
        has_next_book = game_state.next_book()
        if has_next_book:
            # Reveal first character of next book automatically
            game_state.reveal_next_character()
            graph_data = game_state.get_graph_data()
            response_data.update({
                'nextBook': True,
                'graph': graph_data
            })
        else:
            response_data['gameComplete'] = True
    else:
        game_state.score = max(0, game_state.score - 10)
        response_data['score'] = game_state.score
    
    return jsonify(response_data)

@app.route('/skip', methods=['POST'])
def skip():
    has_next_book = game_state.next_book(skip=True)
    if has_next_book:
        # Reveal first character of next book automatically
        game_state.reveal_next_character()
        graph_data = game_state.get_graph_data()
        return jsonify({
            'nextBook': True,
            'currentBook': game_state.current_book_index + 1,
            'totalBooks': game_state.total_books,
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
    return jsonify({
        'success': True,
        'graph': graph_data,
        'score': 100,
        'currentBook': 1,
        'totalBooks': game_state.total_books
    })

if __name__ == '__main__':
    app.run(debug=True)