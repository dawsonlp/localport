# LocalPort Configuration Discoverability Improvement Plan

## Overview
Improve LocalPort's CLI design to make configuration file discovery intuitive and visible to users. Address inconsistent search paths, poor error messages, and lack of visibility about which config file is currently active.

## Implementation Checklist

### Phase 1: Centralize Configuration Path Logic ✅
- [x] **Create centralized config path manager**
  - [x] Create new module: `src/localport/config/config_path_manager.py`
  - [x] Define canonical search paths in one location
  - [x] Add method to detect active config file with status
  - [x] Add method to format config paths for display
  - [x] Add method to generate config status summary

- [x] **Standardize search paths across all components**
  - [x] Update `YamlConfigRepository._find_config_file()` to use centralized paths
  - [x] Update `config_commands.py` hardcoded paths to use centralized logic
  - [x] Remove duplicate search path definitions
  - [x] Ensure consistent search order everywhere

### Phase 2: Enhanced Main Help Display ✅
- [x] **Modify main CLI help to show config status**
  - [x] Update `app.py` main callback to detect config file status
  - [x] Add config status section to main help text
  - [x] Show active config file with `*` marker
  - [x] Display service count from active config
  - [x] Show all search paths in priority order

- [x] **Format config status section**
  - [x] Design clear visual format for config display
  - [x] Add checkmark/X indicators for found/missing files
  - [x] Include file sizes and modification dates
  - [x] Show "(active, X services)" for the current file

### Phase 3: Improve Config Command Help
- [ ] **Update config command group help**
  - [ ] Add "Current config:" line to config --help output
  - [ ] Show current config file path and service count
  - [ ] Display config file status in all config subcommands

- [ ] **Enhance individual config command help**
  - [ ] Update `add_connection_sync` help to mention config location
  - [ ] Update `list_connections_sync` help to show where it reads from
  - [ ] Update `validate_config_sync` help to show default validation target

### Phase 4: Better Error Messages
- [ ] **Improve "config not found" errors**
  - [ ] Replace generic "No configuration file found" messages
  - [ ] Show complete search path list with ✗/✓ indicators
  - [ ] Add helpful suggestions for next steps
  - [ ] Include example config file creation command

- [ ] **Enhance validation error messages**
  - [ ] Show which config file failed validation
  - [ ] Include config file path in validation output
  - [ ] Add line numbers to validation errors where possible

### Phase 5: Config Status Utilities
- [ ] **Add config status command**
  - [ ] Create `localport config status` command
  - [ ] Show detailed config file information
  - [ ] Display search paths with file existence
  - [ ] Show config file permissions and accessibility

- [ ] **Add config initialization command**
  - [ ] Create `localport config init` command  
  - [ ] Interactive config file creation
  - [ ] Choice of config file location
  - [ ] Template-based config generation

### Phase 6: Testing and Validation
- [ ] **Unit tests for config path management**
  - [ ] Test centralized config path logic
  - [ ] Test search path consistency
  - [ ] Test active config detection
  - [ ] Test config status formatting

- [ ] **Integration tests for CLI help**
  - [ ] Test main help shows config status
  - [ ] Test config command help shows current config
  - [ ] Test error messages show search paths
  - [ ] Test config status across different scenarios

- [ ] **End-to-end user experience tests**
  - [ ] Test with no config file present
  - [ ] Test with config in different locations  
  - [ ] Test with invalid/corrupted config files
  - [ ] Test with multiple config files present

## Detailed Implementation Specifications

### Config Path Manager Interface
```python
class ConfigPathManager:
    def get_search_paths(self) -> List[Path]
    def find_active_config(self) -> Optional[ConfigFile]
    def format_config_status(self) -> str
    def format_search_paths(self, show_status: bool = True) -> str
```

### Enhanced Help Output Format
```
Configuration:
  * ~/.config/localport/config.yaml (active, 3 services, 2.1KB)
    ./localport.yaml (not found)
    ~/.localport.yaml (not found)
    /etc/localport/config.yaml (not found)
```

### Improved Error Message Format
```
No configuration file found. Searched:
  ✗ ./localport.yaml
  ✗ ~/.config/localport/config.yaml  
  ✗ ~/.localport.yaml
  ✗ /etc/localport/config.yaml

To get started:
  localport config init          # Create config interactively
  localport config add           # Add your first service
```

## Files to Modify

### Core Files
- [ ] `src/localport/config/config_path_manager.py` (new)
- [ ] `src/localport/cli/app.py` (modify main help)
- [ ] `src/localport/cli/commands/config_commands.py` (update paths and help)
- [ ] `src/localport/infrastructure/repositories/yaml_config_repository.py` (centralize paths)

### Test Files
- [ ] `tests/unit/config/test_config_path_manager.py` (new)
- [ ] `tests/integration/test_config_discoverability.py` (new)
- [ ] Update existing CLI tests to validate config status display

### Documentation Files
- [ ] Update `docs/configuration.md` with accurate search paths
- [ ] Update `docs/getting-started.md` with improved config setup flow
- [ ] Update README.md with clearer config file guidance

## Success Criteria

### User Experience Goals
- [ ] Users can see config file status without remembering special commands
- [ ] Search paths are consistent across all LocalPort components
- [ ] Error messages provide actionable guidance
- [ ] Help text accurately reflects implementation behavior

### Technical Goals
- [ ] Single source of truth for config file search logic
- [ ] Consistent error handling across all config operations
- [ ] Clear separation of concerns between config detection and usage
- [ ] Comprehensive test coverage for config discoverability

## Priority Order

1. **High Priority** - Centralize config path logic and fix inconsistencies
2. **High Priority** - Add config status to main help display  
3. **Medium Priority** - Improve error messages with search paths
4. **Medium Priority** - Enhance config command help text
5. **Low Priority** - Add config status and init commands
6. **Low Priority** - Comprehensive testing and documentation updates

## Estimated Effort
- **Phase 1-2**: 4-6 hours (core functionality)
- **Phase 3-4**: 2-3 hours (UI improvements) 
- **Phase 5**: 2-3 hours (additional commands)
- **Phase 6**: 3-4 hours (testing and validation)
- **Total**: 11-16 hours

## Notes
- Maintain backward compatibility with existing config files
- Preserve all existing functionality while improving discoverability
- Focus on making the default user experience more intuitive
- Consider platform-specific config paths (Windows, macOS, Linux)
