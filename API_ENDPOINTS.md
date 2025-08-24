# CUCares Backend API Endpoints

## Base URL
`http://localhost:8000/api`

## Authentication Endpoints

### Firebase Status Check
- **GET** `/api/firebase-status`
- **Description**: Check Firebase configuration status
- **Response**: Firebase initialization status

### Protected Endpoint (Firebase Auth)
- **POST** `/api/protected`
- **Description**: Protected endpoint that requires Firebase token verification
- **Headers**: `Authorization: Bearer <firebase_token>`
- **Response**: User information if token is valid

## User Management

### Create User
- **POST** `/api/users`
- **Description**: Create a new user with optional file upload
- **Content-Type**: `application/json` or `multipart/form-data`
- **Body**: User data (name, email, phone, etc.)
- **Response**: Created user object

### Get All Users
- **GET** `/api/users`
- **Description**: Get all users with pagination
- **Query Parameters**: 
  - `page` (default: 1)
  - `per_page` (default: 20)
- **Response**: Paginated list of users

### Get Single User
- **GET** `/api/users/{user_id}`
- **Description**: Get a single user by ID
- **Response**: User object

### Update User
- **PUT** `/api/users/{user_id}`
- **Description**: Update a user with optional file upload
- **Content-Type**: `application/json` or `multipart/form-data`
- **Body**: Updated user data
- **Response**: Updated user object

### Delete User
- **DELETE** `/api/users/{user_id}`
- **Description**: Delete a user
- **Response**: Success message

## Organization Management

### Create Organization
- **POST** `/api/orgs`
- **Description**: Create a new organization
- **Body**: Organization data (name, host_user_id, etc.)
- **Response**: Created organization object

### Get All Organizations
- **GET** `/api/orgs`
- **Description**: Get all organizations with pagination
- **Query Parameters**: 
  - `page` (default: 1)
  - `per_page` (default: 20)
- **Response**: Paginated list of organizations

### Get Approved Organizations
- **GET** `/api/orgs/approved`
- **Description**: Get all approved organizations with pagination
- **Query Parameters**: 
  - `page` (default: 1)
  - `per_page` (default: 20)
- **Response**: Paginated list of approved organizations

### Get Unapproved Organizations
- **GET** `/api/orgs/unapproved`
- **Description**: Get all unapproved organizations with pagination
- **Query Parameters**: 
  - `page` (default: 1)
  - `per_page` (default: 20)
- **Response**: Paginated list of unapproved organizations

### Get Single Organization
- **GET** `/api/orgs/{org_id}`
- **Description**: Get a single organization by ID
- **Response**: Organization object

### Update Organization
- **PUT** `/api/orgs/{org_id}`
- **Description**: Update an organization
- **Body**: Updated organization data
- **Response**: Updated organization object

### Delete Organization
- **DELETE** `/api/orgs/{org_id}`
- **Description**: Delete an organization
- **Response**: Success message

## Opportunity Management

### Create Opportunity
- **POST** `/api/opps`
- **Description**: Create a new opportunity with optional file upload
- **Content-Type**: `application/json` or `multipart/form-data`
- **Body**: Opportunity data (name, date, duration, etc.)
- **Response**: Created opportunity object

### Get All Opportunities
- **GET** `/api/opps`
- **Description**: Get all opportunities with pagination
- **Query Parameters**: 
  - `page` (default: 1)
  - `per_page` (default: 20)
- **Response**: Paginated list of opportunities

### Get Single Opportunity
- **GET** `/api/opps/{opp_id}`
- **Description**: Get a single opportunity by ID
- **Response**: Opportunity object

### Update Opportunity
- **PUT** `/api/opps/{opp_id}`
- **Description**: Update an opportunity with optional file upload
- **Content-Type**: `application/json` or `multipart/form-data`
- **Body**: Updated opportunity data
- **Response**: Updated opportunity object

### Delete Opportunity
- **DELETE** `/api/opps/{opp_id}`
- **Description**: Delete an opportunity
- **Response**: Success message

## Registration & Attendance

### Register for Opportunity
- **POST** `/api/register-opp`
- **Description**: Register a user for an opportunity
- **Body**: `{"user_id": 1, "opportunity_id": 2}`
- **Response**: Success message

### Unregister from Opportunity
- **POST** `/api/unregister-opp`
- **Description**: Unregister a user from an opportunity
- **Body**: `{"user_id": 1, "opportunity_id": 2}`
- **Response**: Success message

### Register for Organization
- **POST** `/api/register-org`
- **Description**: Register a user for an organization
- **Body**: `{"user_id": 1, "organization_id": 2}`
- **Response**: Success message

### Unregister from Organization
- **POST** `/api/unregister-org`
- **Description**: Unregister a user from an organization
- **Body**: `{"user_id": 1, "organization_id": 2}`
- **Response**: Success message

### Mark Attendance
- **PUT** `/api/attendance`
- **Description**: Mark a user as attended for an opportunity and award points
- **Body**: `{"user_id": 1, "opportunity_id": 2}`
- **Response**: Success message with points awarded

## Friendship Management

### Get User Friends
- **GET** `/api/users/{user_id}/friends`
- **Description**: Get all accepted friends of a user
- **Response**: List of friend objects

### Get Friend Requests
- **GET** `/api/users/{user_id}/friend-requests`
- **Description**: Get pending friend requests for a user
- **Response**: List of pending friend requests

### Get All Friendships (Admin)
- **GET** `/api/friendships`
- **Description**: Get all friendships in the system (admin endpoint)
- **Response**: List of all friendships

### Get User Friendships
- **GET** `/api/users/{user_id}/friendships`
- **Description**: Get all friendships for a specific user (sent and received)
- **Response**: List of all friendships with status

### Send Friend Request
- **POST** `/api/users/{user_id}/friends`
- **Description**: Send a friend request
- **Body**: `{"receiver_id": 2}`
- **Response**: Success message

### Accept Friend Request
- **PUT** `/api/friendships/{friendship_id}/accept`
- **Description**: Accept a friend request
- **Response**: Success message

### Reject Friend Request
- **PUT** `/api/friendships/{friendship_id}/reject`
- **Description**: Reject a friend request
- **Response**: Success message

### Remove Friend
- **DELETE** `/api/users/{user_id}/friends/{friend_id}`
- **Description**: Remove a friend (delete friendship)
- **Response**: Success message

### Check Friendship Status
- **GET** `/api/users/{user_id}/friends/check/{friend_id}`
- **Description**: Check friendship status between two users
- **Response**: Friendship status object with possible values:
  - `{"status": "no_friendship", "are_friends": false}`
  - `{"status": "request_sent", "are_friends": false}`
  - `{"status": "request_received", "are_friends": false}`
  - `{"status": "friends", "are_friends": true}`

## File Uploads

### Serve Uploaded Files
- **GET** `/static/uploads/{filename}`
- **Description**: Serve uploaded files (images, etc.)
- **Response**: File content

## Error Responses

All endpoints return appropriate HTTP status codes:
- `200`: Success
- `201`: Created
- `400`: Bad Request
- `401`: Unauthorized
- `404`: Not Found
- `500`: Internal Server Error

### Improved Error Handling
All endpoints now include proper error handling for:
- **User not found**: Returns 404 with specific error message
- **Friendship not found**: Returns 404 with detailed error information
- **Invalid operations**: Returns 400 with explanation (e.g., cannot remove pending friend request)

Error responses include:
```json
{
  "message": "Error description",
  "error": "Detailed error information"
}
```

## Pagination

Endpoints that support pagination return:
```json
{
  "data": [...],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 100
  }
}
```
