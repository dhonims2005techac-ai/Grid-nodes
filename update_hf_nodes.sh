#!/bin/bash

echo "========================================="
echo "   GRID NODE UPDATER"
echo "========================================="

WORKER_FILE=~/Grid-nodes/Grid-nodes/worker.py
MASTER_FILE=~/Grid-nodes/Grid-nodes/master.py


# Configure git credentials
git config --global credential.helper store

update_space() {
    SPACE=$1
    TOKEN=$2
    USERNAME=$(echo $SPACE | cut -d'/' -f1)
    
    echo ""
    echo "Updating $SPACE..."
    
    TEMP_DIR=$(mktemp -d)
    
    git clone https://$USERNAME:$TOKEN@huggingface.co/spaces/$SPACE $TEMP_DIR
    
    cp $WORKER_FILE $TEMP_DIR/worker.py
cp $MASTER_FILE $TEMP_DIR/master.py
cp ~/Grid-nodes/Grid-nodes/node_manager.py $TEMP_DIR/node_manager.py
cp ~/Grid-nodes/Grid-nodes/scheduler.py $TEMP_DIR/scheduler.py
cp ~/Grid-nodes/Grid-nodes/database.py $TEMP_DIR/database.py
cp ~/Grid-nodes/Grid-nodes/analytics.py $TEMP_DIR/analytics.py
cp ~/Grid-nodes/Grid-nodes/job_queue.py $TEMP_DIR/job_queue.py
cp ~/Grid-nodes/Grid-nodes/benchmark.py $TEMP_DIR/benchmark.py
    
    cd $TEMP_DIR
git remote set-url origin https://$USERNAME:$TOKEN@huggingface.co/spaces/$SPACE
    
    git add worker.py master.py \
node_manager.py scheduler.py \
database.py analytics.py \
job_queue.py benchmark.py
    git commit -m "Update worker.py and master.py" || true
    git push
    
    cd ~
    rm -rf $TEMP_DIR
    
    echo "✅ $SPACE updated!"
}

update_space "Bug-spy1/Grid222" "$BUG_TOKEN"
update_space "Bug-spy1/GridnodeHF5" "$BUG_TOKEN"

update_space "dhoni22/GridnodeHF8" "$DHONI22_TOKEN"
update_space "dhoni22/gridnodeHF7" "$DHONI22_TOKEN"

update_space "Bug-spy1/GridnodeHF6" "$BUG_TOKEN"
update_space "done1237/gridnodeHF9" "$DONE_TOKEN"

update_space "dhonims/Grid333" "$DHONIMS_TOKEN"
update_space "dhonims/gridnodehf11" "$DHONIMS_TOKEN"

update_space "dhoni22/girdtest" "$DHONI22_TOKEN"
update_space "done1237/Gridc" "$DONE_TOKEN"

update_space "done1237/GridnodeHF10" "$DONE_TOKEN"

update_space "dhonims/Grid12" "$DHONIMS_TOKEN"

echo ""
echo "========================================="
echo "All 12 HF Spaces updated successfully!"
echo "========================================="

