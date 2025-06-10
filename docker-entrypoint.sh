#!/bin/sh

# Apply database migrations
echo "Applying database migrations..."
python manage.py migrate

# Create a superuser if it doesn't exist
echo "Creating superuser..."
python manage.py create_superuser_auto

# Start server
echo "Starting server"
exec "$@" 