# LocalPort v0.3.7.1 Release Notes

**Release Date**: January 5, 2025  
**Release Type**: Patch (Bug Fix)  
**Priority**: High

## Overview

LocalPort v0.3.7.1 is a critical patch release that fixes important issues in the cluster health monitoring system introduced in v0.3.7. This release ensures accurate node count displays, improves performance, and maintains architectural integrity.

## 🐛 Bug Fixes

### Cluster Health Monitoring
- **Fixed node count display**: Cluster health now correctly shows actual node counts (e.g., 3 nodes) instead of 0
- **Improved performance**: Status commands now respond significantly faster with optimized kubectl client usage
- **Fixed time calculations**: Resolved negative time displays like "-17999s ago", now shows accurate "0s ago", "2m ago", etc.
- **Optimized UI layout**: Removed API Server column from main status command to prevent truncation, kept in dedicated cluster status command

## 🏗️ Technical Improvements

### Architecture
- **Preserved domain model integrity**: Maintained proper `ClusterHealth` domain entities throughout the system
- **Consistent lightweight pattern**: Both status and cluster commands use the same fast kubectl client approach
- **Better error handling**: Improved timezone handling and object property access

### Performance
- **Faster status commands**: Reduced timeout from heavy monitoring setup to lightweight 10-second checks
- **Optimized cluster queries**: Direct kubectl client usage instead of full cluster health manager initialization

## 📋 What's Changed

### Files Modified
- `src/localport/cli/commands/service_commands.py` - Fixed cluster health integration in main status command
- `src/localport/cli/commands/cluster_commands.py` - Optimized dedicated cluster status command

### Key Technical Changes
1. **Proper Domain Entity Usage**: Fixed to use `ClusterHealth.create_healthy()` factory method
2. **Lightweight kubectl Client**: Replaced heavy cluster health manager with fast kubectl client
3. **Fixed Timezone Handling**: Proper UTC timezone calculations with negative value protection
4. **UI Layout Optimization**: Removed truncated columns for better readability

## 🔄 Upgrade Instructions

```bash
# Update LocalPort
pip install --upgrade localport==0.3.7.1

# Verify the fixes
localport status
localport cluster status
```

## ✅ Expected Results After Upgrade

- Node counts display correctly (actual values, not 0)
- Time calculations show positive values ("0s ago", "2m ago", etc.)
- Commands respond quickly (< 10 seconds)
- Clean, readable table layouts without truncation
- All existing functionality continues to work unchanged

## 🔧 Compatibility

- **Backward Compatible**: No breaking changes to configuration or APIs
- **Dependencies**: No new dependencies added
- **Configuration**: Existing cluster health settings continue to work

## 🎯 Impact

### User Experience
- ✅ Accurate cluster health information
- ✅ Faster command response times
- ✅ Cleaner, more readable displays
- ✅ Reliable timing information

### System Stability
- ✅ No disruption to port forwarding services
- ✅ Maintained architectural quality
- ✅ Improved error handling

## 🔍 Verification

### Before v0.3.7.1
```
🏗️  Cluster Health
┃ Context              ┃ Status     ┃ Nodes ┃ Pods ┃ Last Check   ┃
┃ dev-hybrid-us-east-1 ┃ 🔴 Error   ┃ 0     ┃ 26   ┃ -17999s ago  ┃
```

### After v0.3.7.1
```
🏗️  Cluster Health
┃ Context              ┃ Status       ┃ Nodes ┃ Pods ┃ Last Check ┃
┃ dev-hybrid-us-east-1 ┃ 🟢 Healthy   ┃ 3     ┃ 26   ┃ 0s ago     ┃
```

## 📚 Documentation

- [Cluster Health Monitoring Guide](docs/cluster-health-monitoring.md)
- [Configuration Reference](docs/configuration.md)
- [Troubleshooting Guide](docs/troubleshooting.md)

## 🙏 Acknowledgments

This release addresses critical issues identified during production usage and ensures LocalPort's cluster health monitoring provides accurate, reliable information for Kubernetes environments.

---

For detailed technical information about the fixes, see [LOCALPORT_V0.3.7.1_CLUSTER_HEALTH_FIXES.md](LOCALPORT_V0.3.7.1_CLUSTER_HEALTH_FIXES.md).
