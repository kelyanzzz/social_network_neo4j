# social_network.py
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import sqlite3
from dataclasses import dataclass
from typing import List, Optional
from neo4j import GraphDatabase

# ======================
# Database Access Layer
# ======================
class Database:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            "neo4j+s://db8f05bc.databases.neo4j.io",
            auth=("db8f05bc", "LFbdedVkAkHx9cnjoEqFJGHA0b_JPeJ-2OSSdWUKg0I")
        )
        self._init_db()

    def _init_db(self):
        with self.driver.session() as session:
            session.run("CREATE CONSTRAINT unique_user_id IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE")
            session.run("CREATE CONSTRAINT unique_username IF NOT EXISTS FOR (u:User) REQUIRE u.username IS UNIQUE")
            print("Constraints added")

    def close(self):
        self.driver.close()

    # User operations
    def create_user(self, username: str, name: str) -> int:
        query = """
        OPTIONAL MATCH (u:User)
        WITH COALESCE(MAX(u.id), 0) + 1 AS new_id
        CREATE (new_user:User {id: new_id, username: $username, name: $name})
        RETURN new_user.id AS id
        """
        records, summary, keys = self.driver.execute_query(query, username=username, name=name)
        return records[0]["id"]

    def get_user(self, user_id: int) -> Optional[dict]:
        query = "MATCH (u:User {id: $user_id}) RETURN u.id AS id, u.username AS username, u.name AS name"
        records, summary, keys = self.driver.execute_query(query, user_id=user_id)
        if records:
            return dict(records[0])
        return None

    def get_all_users(self) -> List[dict]:
        query = "MATCH (u:User) RETURN u.id AS id, u.username AS username, u.name AS name ORDER BY u.id"
        records, summary, keys = self.driver.execute_query(query)
        return [dict(record) for record in records]
    
    # Post operations
    # Post operations
    def create_post(self, user_id: int, content: str) -> int:
        query = """
        MATCH (u:User {id: $user_id})
        OPTIONAL MATCH (all_posts:Post)
        WITH u, COALESCE(MAX(all_posts.id), 0) + 1 AS new_post_id
        CREATE (p:Post {
            id: new_post_id, 
            content: $content, 
            timestamp: toString(localdatetime())
        })
        CREATE (u)-[:POSTED]->(p)
        RETURN p.id AS id
        """
        records, summary, keys = self.driver.execute_query(query, user_id=user_id, content=content)
        return records[0]["id"]

    def get_posts_by_user(self, user_id: int) -> List[dict]:
        query = """
        MATCH (u:User {id: $user_id})-[:POSTED]->(p:Post)
        RETURN p.id AS id, p.content AS content, p.timestamp AS timestamp, u.username AS username, u.name AS name
        ORDER BY p.timestamp DESC
        """
        records, summary, keys = self.driver.execute_query(query, user_id=user_id)
        return [dict(record) for record in records]
    def get_feed(self, user_id: int) -> List[dict]:
        query = """
        MATCH (u:User {id: $user_id})-[:FOLLOWS]->(followee:User)-[:POSTED]->(p:Post)
        RETURN p.id AS id, p.content AS content, p.timestamp AS timestamp, 
               followee.username AS username, followee.name AS name
        ORDER BY p.timestamp DESC
        """
        records, summary, keys = self.driver.execute_query(query, user_id=user_id)
        return [dict(record) for record in records]



    
    # Follow operations
    def follow_user(self, follower_id: int, followee_id: int) -> bool:
        query = """
        MATCH (follower:User {id: $follower_id}), (followee:User {id: $followee_id})
        MERGE (follower)-[:FOLLOWS]->(followee)
        """
        try:
            self.driver.execute_query(query, follower_id=follower_id, followee_id=followee_id)
            return True
        except Exception as e:
            print(f"Error following user: {e}")
            return False

    def get_followers(self, user_id: int) -> List[dict]:
        query = """
        MATCH (u:User {id: $user_id})<-[:FOLLOWS]-(follower:User)
        RETURN follower.id AS id, follower.username AS username, follower.name AS name
        """
        records, summary, keys = self.driver.execute_query(query, user_id=user_id)
        return [dict(record) for record in records]

    def get_following(self, user_id: int) -> List[dict]:
        query = """
        MATCH (u:User {id: $user_id})-[:FOLLOWS]->(followee:User)
        RETURN followee.id AS id, followee.username AS username, followee.name AS name
        """
        records, summary, keys = self.driver.execute_query(query, user_id=user_id)
        return [dict(record) for record in records]

    def unfollow_user(self, follower_id: int, followee_id: int) -> bool:
        query = """
        MATCH (follower:User {id: $follower_id})-[r:FOLLOWS]->(followee:User {id: $followee_id})
        DELETE r
        """
        try:
            self.driver.execute_query(query, follower_id=follower_id, followee_id=followee_id)
            return True
        except Exception as e:
            print(f"Error unfollowing user: {e}")
            return False
# ======================
# Web Application
# ======================
app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
db = Database()

# Sample data initialization
with app.app_context():
    # Create some sample users if they don't exist
    if not db.get_all_users():
        db.create_user('alice', 'Alice Smith')
        db.create_user('bob', 'Bob Johnson')
        db.create_user('charlie', 'Charlie Brown')

# ======================
# API Endpoints
# ======================
@app.route('/api/users', methods=['GET'])
def api_get_users():
    return jsonify(db.get_all_users())

@app.route('/api/users/<int:user_id>', methods=['GET'])
def api_get_user(user_id):
    user = db.get_user(user_id)
    return jsonify(user) if user else ('User not found', 404)

@app.route('/api/users/<int:user_id>/posts', methods=['GET'])
def api_get_user_posts(user_id):
    return jsonify(db.get_posts_by_user(user_id))

@app.route('/api/users/<int:user_id>/feed', methods=['GET'])
def api_get_user_feed(user_id):
    return jsonify(db.get_feed(user_id))

@app.route('/api/users/<int:user_id>/followers', methods=['GET'])
def api_get_user_followers(user_id):
    return jsonify(db.get_followers(user_id))

@app.route('/api/users/<int:user_id>/following', methods=['GET'])
def api_get_user_following(user_id):
    return jsonify(db.get_following(user_id))

@app.route('/api/posts', methods=['POST'])
def api_create_post():
    data = request.get_json()
    post_id = db.create_post(data['user_id'], data['content'])
    return jsonify({'post_id': post_id}), 201

@app.route('/api/follow', methods=['POST'])
def api_follow_user():
    data = request.get_json()
    success = db.follow_user(data['follower_id'], data['followee_id'])
    return jsonify({'success': success}), 201 if success else 200

# ======================
# Frontend Routes
# ======================
@app.route('/')
def home():
    users = db.get_all_users()
    current_user = None
    if 'user_id' in session:
        current_user = db.get_user(session['user_id'])
    return render_template('index.html', users=users, current_user=current_user)

@app.route('/user/<int:user_id>')
def user_profile(user_id):
    user = db.get_user(user_id)
    if not user:
        return "User not found", 404
        
    current_user = None
    is_following = False
    
    if 'user_id' in session:
        current_user = db.get_user(session['user_id'])
        if current_user and current_user['id'] != user_id:
            # Check if current user is following this profile user
            following = db.get_following(current_user['id'])
            is_following = any(f['id'] == user_id for f in following)
    
    posts = db.get_posts_by_user(user_id)
    followers = db.get_followers(user_id)
    following = db.get_following(user_id)
    
    return render_template('profile.html', 
                         user=user, 
                         posts=posts,
                         followers=followers,
                         following=following,
                         current_user=current_user,
                         is_following=is_following)

@app.route('/user/<int:user_id>/feed')
def user_feed(user_id):
    user = db.get_user(user_id)
    feed = db.get_feed(user_id)
    return render_template('feed.html', user=user, feed=feed)

@app.route('/create_post', methods=['POST'])
def create_post():
    user_id = int(request.form['user_id'])
    content = request.form['content']
    db.create_post(user_id, content)
    return redirect(url_for('user_profile', user_id=user_id))

@app.route('/login/<int:user_id>')
def login(user_id):
    session['user_id'] = user_id
    return redirect(url_for('home'))

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('home'))

@app.route('/follow', methods=['POST'])
def follow():
    follower_id = int(request.form['follower_id'])
    followee_id = int(request.form['followee_id'])
    
    # Check if the user is already following
    following = db.get_following(follower_id)
    is_following = any(f['id'] == followee_id for f in following)
    
    if is_following:
        # Implement unfollow functionality (you'll need to add this to your Database class)
        db.unfollow_user(follower_id, followee_id)
    else:
        db.follow_user(follower_id, followee_id)
    
    return redirect(url_for('user_profile', user_id=followee_id))

# ======================
# HTML Templates
# ======================
@app.route('/templates/<template_name>')
def serve_template(template_name):
    return render_template(template_name)

# Template rendering functions
app.jinja_env.globals.update(
    render_index=lambda: render_template('index.html', users=db.get_all_users()),
    render_profile=lambda user_id: render_template(
        'profile.html',
        user=db.get_user(user_id),
        posts=db.get_posts_by_user(user_id),
        followers=db.get_followers(user_id),
        following=db.get_following(user_id)
    )
)

if __name__ == '__main__':
    app.run(debug=True)