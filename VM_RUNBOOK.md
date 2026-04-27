# Oracle VM Runbook — StockTweetAnalyze

**VM IP:** `150.136.171.185`
**SSH Key:** `C:\Users\Sunny\.ssh\oracle_vm.key`

---

## Connect to VM

```bash
ssh -i C:\Users\Sunny\.ssh\oracle_vm.key ubuntu@150.136.171.185
```

---

## App Service (stocktweet)

```bash
# Status
sudo systemctl status stocktweet --no-pager

# Start
sudo systemctl start stocktweet

# Stop
sudo systemctl stop stocktweet

# Restart (after code update)
sudo systemctl restart stocktweet
```

---

## View Logs

```bash
# Live log stream (Ctrl+C to exit)
sudo journalctl -u stocktweet -f

# Last 50 lines
sudo journalctl -u stocktweet -n 50 --no-pager

# Errors only
sudo journalctl -u stocktweet -p err --no-pager

# nginx access log
sudo tail -20 /var/log/nginx/access.log

# nginx error log
sudo tail -20 /var/log/nginx/error.log
```

---

## Sync Clippings from GitHub

```bash
# Pull latest tweets from obsidian-clippings repo
cd /home/ubuntu/clippings && git pull

# Check how many clippings are on the VM
ls /home/ubuntu/clippings | wc -l

# See most recently added clippings
ls -t /home/ubuntu/clippings | head -10
```

---

## Update App from GitHub

```bash
cd /home/ubuntu/app && git pull
sudo systemctl restart stocktweet
sudo systemctl restart nginx
```

---

## nginx

```bash
# Status
sudo systemctl status nginx --no-pager

# Restart
sudo systemctl restart nginx

# Test config
sudo nginx -t
```

---

## Check Everything is Running

```bash
sudo systemctl status stocktweet --no-pager
sudo systemctl status nginx --no-pager
curl http://localhost:8000/api/feed
```

---

## Disk & Memory

```bash
# Memory usage
free -h

# Disk usage
df -h

# What's using the most memory
ps aux --sort=-%mem | head -10
```

---

## Cron Jobs

```bash
# View cron jobs (clippings git pull every 30 min)
crontab -l

# Edit cron jobs
crontab -e
```

---

## App URL

**Live app:** http://150.136.171.185
