import sqlite3
from neo4j import GraphDatabase

# SQLite connection
sqlite_conn = sqlite3.connect('social_network.db')
sqlite_conn.row_factory = sqlite3.Row
cur = sqlite_conn.cursor()

# Neo4j connection
driver = GraphDatabase.driver(
    "neo4j+s://db8f05bc.databases.neo4j.io",
    auth=("db8f05bc", "LFbdedVkAkHx9cnjoEqFJGHA0b_JPeJ-2OSSdWUKg0I")
)

# 1. Read from SQLite
users = cur.execute("SELECT * FROM users").fetchall()
posts = cur.execute("SELECT * FROM posts").fetchall()
follows = cur.execute("SELECT * FROM followers").fetchall()

sqlite_conn.close()
print(f"Read {len(users)} users, {len(posts)} posts, {len(follows)} follows")

# 2. Insert users into Neo4j
with driver.session() as session:
    for user in users:
        session.run("""
            MERGE (u:User {id: $id})
            SET u.username = $username, u.name = $name
        """, id=user["id"], username=user["username"], name=user["name"])
    print("Users migrated!")

    # 3. Insert posts into Neo4j
    for post in posts:
        session.run("""
            MATCH (u:User {id: $user_id})
            MERGE (p:Post {id: $id})
            SET p.content = $content, p.timestamp = $timestamp
            MERGE (u)-[:POSTED]->(p)
        """, id=post["id"], user_id=post["user_id"], content=post["content"], timestamp=post["timestamp"])
    print("Posts migrated!")

    # 4. Insert follows into Neo4j
    for follow in follows:
        session.run("""
            MATCH (a:User {id: $follower_id}), (b:User {id: $followee_id})
            MERGE (a)-[:FOLLOWS]->(b)
        """, follower_id=follow["follower_id"], followee_id=follow["followee_id"])
    print("Follows migrated!")

driver.close()
print("Migration complete!")