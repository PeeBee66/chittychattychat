#!/bin/bash

# Certificate Management Helper for ChittyChattyChat
# Easy switching between development and production certificates

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Functions
show_status() {
    echo -e "\n${CYAN}📊 Current Certificate Status:${NC}"

    # Check for dev certificates
    if [ -d "certs/nginx" ] && [ -f "certs/nginx/chat.crt" ]; then
        echo -e "  ${GREEN}✓${NC} Development certificates found in certs/nginx/"
    else
        echo -e "  ${YELLOW}○${NC} No development certificates found"
    fi

    # Check for Let's Encrypt certificates
    if [ -d "certs/letsencrypt/live" ]; then
        echo -e "  ${GREEN}✓${NC} Let's Encrypt certificates found in certs/letsencrypt/"
        ls -la certs/letsencrypt/live/ 2>/dev/null | grep -E "^d" | awk '{print "    - " $9}' | grep -v "^\s*-\s*$"
    else
        echo -e "  ${YELLOW}○${NC} No Let's Encrypt certificates found"
    fi

    # Check current Docker status
    echo -e "\n${CYAN}🐳 Docker Status:${NC}"
    if docker-compose ps | grep -q "ccc-nginx"; then
        echo -e "  ${GREEN}✓${NC} Nginx container is running"

        # Check which config is active
        if docker-compose ps | grep -q "ccc-certbot"; then
            echo -e "  ${GREEN}✓${NC} Certbot container is running (Production mode)"
        else
            echo -e "  ${YELLOW}○${NC} Certbot container not running (Development mode)"
        fi
    else
        echo -e "  ${YELLOW}○${NC} Nginx container is not running"
    fi
}

use_dev_certificates() {
    echo -e "\n${BLUE}🔧 Switching to Development Certificates...${NC}"

    # Check if dev certificates exist
    if [ ! -f "certs/nginx/chat.crt" ]; then
        echo -e "${YELLOW}Development certificates not found. Generating...${NC}"
        ./generate-dev-certs.sh
    fi

    # Update Nginx configuration for dev certificates
    echo -e "${GREEN}Updating Nginx configuration...${NC}"

    # Stop services
    docker-compose down

    # Start with development configuration
    docker-compose up -d

    echo -e "${GREEN}✅ Switched to development certificates!${NC}"
    echo -e "   Access services at:"
    echo -e "   ${BLUE}https://localhost${NC} or ${BLUE}https://chat.chittychattychat.local${NC}"
}

use_production_certificates() {
    echo -e "\n${BLUE}🔧 Switching to Production (Let's Encrypt) Certificates...${NC}"

    # Check if Let's Encrypt certificates exist
    if [ ! -d "certs/letsencrypt/live" ]; then
        echo -e "${RED}❌ Let's Encrypt certificates not found!${NC}"
        echo -e "   Please run ${BLUE}./setup-letsencrypt.sh${NC} first to configure Let's Encrypt"
        exit 1
    fi

    # Check if docker-compose.letsencrypt.yml exists
    if [ ! -f "docker-compose.letsencrypt.yml" ]; then
        echo -e "${RED}❌ docker-compose.letsencrypt.yml not found!${NC}"
        echo -e "   Please run ${BLUE}./setup-letsencrypt.sh${NC} first"
        exit 1
    fi

    # Stop services
    docker-compose down

    # Start with production configuration
    docker-compose -f docker-compose.yml -f docker-compose.letsencrypt.yml up -d

    echo -e "${GREEN}✅ Switched to production certificates!${NC}"
    echo -e "   Services should be accessible at your configured domains"
}

check_certificate_expiry() {
    echo -e "\n${CYAN}📅 Certificate Expiry Dates:${NC}"

    # Check dev certificates
    if [ -f "certs/nginx/chat.crt" ]; then
        echo -e "\n  ${BLUE}Development Certificates:${NC}"
        expiry_date=$(openssl x509 -in certs/nginx/chat.crt -noout -enddate | cut -d= -f2)
        echo -e "    Chat cert expires: ${expiry_date}"

        if [ -f "certs/nginx/admin.crt" ]; then
            expiry_date=$(openssl x509 -in certs/nginx/admin.crt -noout -enddate | cut -d= -f2)
            echo -e "    Admin cert expires: ${expiry_date}"
        fi
    fi

    # Check Let's Encrypt certificates
    if [ -d "certs/letsencrypt/live" ]; then
        echo -e "\n  ${BLUE}Let's Encrypt Certificates:${NC}"
        for domain_dir in certs/letsencrypt/live/*/; do
            if [ -d "$domain_dir" ] && [ -f "${domain_dir}cert.pem" ]; then
                domain=$(basename "$domain_dir")
                expiry_date=$(openssl x509 -in "${domain_dir}cert.pem" -noout -enddate | cut -d= -f2)
                echo -e "    ${domain}: ${expiry_date}"
            fi
        done
    fi
}

renew_letsencrypt() {
    echo -e "\n${BLUE}🔄 Checking Let's Encrypt certificate renewal...${NC}"

    if [ ! -f "renew-certificates.sh" ]; then
        echo -e "${RED}❌ renew-certificates.sh not found!${NC}"
        echo -e "   Please run ${BLUE}./setup-letsencrypt.sh${NC} first"
        exit 1
    fi

    ./renew-certificates.sh
}

backup_certificates() {
    echo -e "\n${BLUE}💾 Backing up certificates...${NC}"

    backup_dir="certs-backup-$(date +%Y%m%d-%H%M%S)"

    if [ -d "certs" ]; then
        cp -r certs "$backup_dir"
        echo -e "${GREEN}✅ Certificates backed up to ${backup_dir}/${NC}"

        # Create tar archive
        tar -czf "${backup_dir}.tar.gz" "$backup_dir"
        rm -rf "$backup_dir"
        echo -e "${GREEN}✅ Archive created: ${backup_dir}.tar.gz${NC}"
    else
        echo -e "${YELLOW}⚠️  No certificates directory found to backup${NC}"
    fi
}

# Main menu
show_menu() {
    echo -e "\n${CYAN}========================================${NC}"
    echo -e "${CYAN}  ChittyChattyChat Certificate Manager${NC}"
    echo -e "${CYAN}========================================${NC}"
    echo -e "\nChoose an option:"
    echo -e "  ${BLUE}1)${NC} Show current status"
    echo -e "  ${BLUE}2)${NC} Use development certificates (self-signed)"
    echo -e "  ${BLUE}3)${NC} Use production certificates (Let's Encrypt)"
    echo -e "  ${BLUE}4)${NC} Generate new development certificates"
    echo -e "  ${BLUE}5)${NC} Setup Let's Encrypt (first time)"
    echo -e "  ${BLUE}6)${NC} Renew Let's Encrypt certificates"
    echo -e "  ${BLUE}7)${NC} Check certificate expiry dates"
    echo -e "  ${BLUE}8)${NC} Backup certificates"
    echo -e "  ${BLUE}9)${NC} Exit"
    echo -n -e "\nSelect option: "
}

# Command line arguments
if [ $# -gt 0 ]; then
    case "$1" in
        status)
            show_status
            ;;
        dev)
            use_dev_certificates
            ;;
        prod|production)
            use_production_certificates
            ;;
        renew)
            renew_letsencrypt
            ;;
        backup)
            backup_certificates
            ;;
        expiry)
            check_certificate_expiry
            ;;
        *)
            echo -e "${RED}Unknown command: $1${NC}"
            echo -e "Usage: $0 [status|dev|prod|renew|backup|expiry]"
            exit 1
            ;;
    esac
    exit 0
fi

# Interactive mode
while true; do
    show_menu
    read -r choice

    case $choice in
        1)
            show_status
            ;;
        2)
            use_dev_certificates
            ;;
        3)
            use_production_certificates
            ;;
        4)
            ./generate-dev-certs.sh
            ;;
        5)
            if [ -f "setup-letsencrypt.sh" ]; then
                ./setup-letsencrypt.sh
            else
                echo -e "${RED}❌ setup-letsencrypt.sh not found!${NC}"
            fi
            ;;
        6)
            renew_letsencrypt
            ;;
        7)
            check_certificate_expiry
            ;;
        8)
            backup_certificates
            ;;
        9)
            echo -e "${GREEN}Goodbye!${NC}"
            exit 0
            ;;
        *)
            echo -e "${RED}Invalid option!${NC}"
            ;;
    esac

    echo -e "\n${YELLOW}Press Enter to continue...${NC}"
    read -r
done