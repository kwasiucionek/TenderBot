#!/bin/bash
#!/bin/bash
cd /home/kwasiucionek/TenderBot
TENDERBOT_USE_PUSHER=yes \
/home/kwasiucionek/miniconda3/bin/python3 notifier.py >> logs/notifier.log 2>&1
