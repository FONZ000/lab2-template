from flask import Flask, request, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
from os import environ
import uuid

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = environ.get('DB_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Loyalty(db.Model):
    __tablename__ = 'loyalty'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    reservation_count = db.Column(db.Integer, default=0, nullable=False)
    status = db.Column(db.String(80), default='BRONZE', nullable=False)
    discount = db.Column(db.Integer, default=5, nullable=False)

    def json(self):
        return {
            'id': self.id,
            'username': self.username,
            'reservation_count': self.reservation_count,
            'status': self.status,
            'discount': self.discount
        }

    def update_status(self):
        if self.reservation_count >= 20:
            self.status = 'GOLD'
            self.discount = 10
        elif self.reservation_count >= 15:
            self.status = 'SILVER'
            self.discount = 7
        elif self.reservation_count >= 10:
            self.status = 'BRONZE'
            self.discount = 5
        else:
            self.status = 'UNDEFINED'
            self.discount = 0

with app.app_context():
    db.create_all()



#Create new user
@app.route('/loyalty', methods=['POST'])
def create_loyalty_user():
    data = request.get_json()
    if not data or 'username' not in data or 'reservation_count' not in data or 'status' not in data or 'discount' not in data:
        return make_response(jsonify({'message': 'Username is required'}), 400)

    username = data['username']
    reservation_count = data['reservation_count']
    status = data['status']
    discount = data['discount']

    existing_user = Loyalty.query.filter_by(username=username).first()
    if existing_user:
        return make_response(jsonify({'message': f'User {username} already exists'}), 409)

    user = Loyalty(
        username=username, 
        reservation_count=reservation_count, 
        status=status, 
        discount=discount
    )

    db.session.add(user)
    db.session.commit()

    return make_response(jsonify({'message': f'User {username} created successfully'}), 201)

#get user info
@app.route('/loyalty/<username>', methods=['GET'])
def get_loyalty_user_by_username(username):
    user = Loyalty.query.filter_by(username=username).first()
    if not user:
        return make_response(jsonify({'message': f'User {username} not found'}), 404)
    return make_response(jsonify(user.json()), 200)


#update user
@app.route('/loyalty/<username>/', methods=['PATCH'])
def update_loyalty_user(username):
    data = request.get_json()
    if not data or 'reservation_count' not in data:
        return make_response(jsonify({'message': 'reservation_count is required'}), 400)
    
    user = Loyalty.query.filter_by(username=username).first()
    if not user:
        return make_response(jsonify({'message': f'User {username} not found'}), 404)

    try:
        user.reservation_count = data['reservation_count']
        user.update_status()
        db.session.commit()
        return make_response(jsonify({'message': f'User {username} updated successfully'}), 200)

    except Exception as e:
        return make_response(jsonify({'message': f'Error updating user: {str(e)}'}), 500)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=True)
