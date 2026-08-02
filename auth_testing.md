# MidGate Auth Testing

Auth: email/password JWT with httpOnly cookies (access_token 60m + refresh_token 7d).
bcrypt password hashing. Brute-force lockout: 5 fails => 15 min per ip:email.

## Admin
- admin@midgate.io / Admin123!

## Flows to verify
1. Register -> creates user + default workspace, sets cookies, returns {user, workspaces, current_workspace}.
2. Login -> sets cookies, returns user + workspaces.
3. /api/auth/me with cookie -> returns current user + workspaces.
4. Logout -> clears cookies.
5. Forgot password -> logs reset link to backend logs; reset-password with token updates hash.
6. Duplicate email register -> 409.
7. Wrong password -> 401; 5x -> 429 lockout.

## curl
curl -c c.txt -X POST http://localhost:8001/api/auth/login -H "Content-Type: application/json" -d '{"email":"admin@midgate.io","password":"Admin123!"}'
curl -b c.txt http://localhost:8001/api/auth/me
