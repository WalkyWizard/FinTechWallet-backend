В цьому Fast API є такі ендпоіти:
1. Auth
   1. POST auth/register - регістрація нового акаунту
   2. POST auth/login - авторизація користувача
   3. POST auth/swagger-login - авторизація користувача у свагері
2. Wallets (потрібна авторизація)
   1. POST /wallets/ - створення гаманця
   2. GET /wallets/user - виведення всіх гаманців користувача
   3. GET /wallets/user/{wallet_id} - виведення одно конкретного гаманця користувача
3. Transactions (потрібна авторизація)
   1. POST /transactions/deposit - поповнення балансу гаманця
   2. POST /transactions/withdraw - виведення коштів з гаманця
   3. POST /transactions/transfer - пеереведення коштів зі свого гаманця на інший
   4. GET /transactions/pending - виведення всіх надісланих переказів до гаманця
   5. POST /transactions/{transaction_id}/accept - підтвердження надісланого переказу
   6. POST /transactions/{transaction_id}/reject - відхилення надісланого переказу
   7. GET /transactions/history/{wallet_id} - виведення історії транзакцій гаманця
4. Admin (доступ мають тільки адміни)
   1. GET /admin/users - отримання списку всіх користувачів (окрім адмінів)
   2. POST /admin/block - заблокувати акаунт користувача
   3. POST /admin/unblock - розблокувати акаунт користувача
   4. GET /admin/transactions - отримання списку усіх транзакцій (з фільтром по типу транзакції та по користувачу)
