-- Create databases for Django and bridges
-- Use simple CREATE DATABASE statements for all but nexus_db
-- nexus_db is already created via POSTGRES_DB env variable

CREATE DATABASE synapse_db;
CREATE DATABASE whatsapp_bridge_db;
CREATE DATABASE telegram_bridge_db;
CREATE DATABASE instagram_bridge_db;
CREATE DATABASE facebook_bridge_db;
CREATE DATABASE signal_bridge_db;

-- Grant permissions to nexus_user for all databases (bridges will use nexus_user credentials)
GRANT ALL PRIVILEGES ON DATABASE nexus_db TO nexus_user;
GRANT ALL PRIVILEGES ON DATABASE synapse_db TO nexus_user;
GRANT ALL PRIVILEGES ON DATABASE whatsapp_bridge_db TO nexus_user;
GRANT ALL PRIVILEGES ON DATABASE telegram_bridge_db TO nexus_user;
GRANT ALL PRIVILEGES ON DATABASE instagram_bridge_db TO nexus_user;
GRANT ALL PRIVILEGES ON DATABASE facebook_bridge_db TO nexus_user;
GRANT ALL PRIVILEGES ON DATABASE signal_bridge_db TO nexus_user;
