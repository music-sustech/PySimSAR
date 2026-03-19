# Contract: Extended HDF5 Schema

## Schema v2 (backwards-compatible with v1)

Existing groups (`/metadata`, `/config`, `/raw_data`, `/navigation`, `/images`) unchanged. New `/parameters` group added.

```
/metadata
  @software_version            # "pySimSAR 0.2.0"
  @creation_date               # ISO 8601
  @coordinate_system           # "ENU"
  @origin_lat, @origin_lon, @origin_alt
  @schema_version              # NEW: "2.0" (absent in v1 files)

/parameters                    # NEW GROUP — complete project parameter set
  @format_version              # "1.0" (matches project.json version)

  /scene
    @origin_lat_deg, @origin_lon_deg, @origin_alt_m
    /point_targets
      positions                # dataset (n, 3) float64
      rcs                      # dataset (n,) float64 or (n, 2, 2) complex128
      velocities               # dataset (n, 3) float64 (zeros if stationary)
    /distributed_targets
      /target_{i}
        @origin_m              # [x, y, z]
        @extent_m              # [dx, dy]
        @cell_size_m           # float
        reflectivity           # dataset (ny, nx) float64 [optional]
        elevation              # dataset (ny, nx) float64 [optional]

  /radar
    @carrier_freq_hz, @prf_hz, @transmit_power_w
    @receiver_gain_dB, @noise_figure_dB, @system_losses_dB
    @reference_temp_K, @squint_angle_rad, @depression_angle_rad
    @polarization              # "single" | "dual" | "quad"
    @mode                      # "stripmap" | "spotlight" | "scanmar"
    @look_side                 # "left" | "right"
    /waveform
      @type                    # "lfm" | "fmcw"
      @bandwidth_hz, @duty_cycle
      @ramp_type               # "up" | "down" | "triangle" (FMCW only)
      @window                  # "hamming" | "hanning" | ... | null
      @phase_noise_enabled     # bool
      @flicker_fm_level_dBc, @white_fm_level_dBc  # if enabled
      @flicker_pm_level_dBc, @white_floor_dBc     # if enabled
    /antenna
      @preset                  # "flat" | "sinc" | "gaussian" | "custom"
      @az_beamwidth_rad, @el_beamwidth_rad
      @peak_gain_dB
      pattern_2d               # dataset (n_el, n_az) float32 [optional, for custom]
      az_angles                # dataset (n_az,) float64 [optional]
      el_angles                # dataset (n_el,) float64 [optional]

  /platform
    @velocity_mps, @altitude_m
    @heading                   # JSON array [hx, hy, hz] or scalar radians
    start_position             # dataset (3,) float64
    stop_position              # dataset (3,) float64 [optional, for start-stop mode]
    @flight_path_mode          # "start_stop" | "heading_time"
    @flight_time_s             # [optional, for heading_time mode]
    @perturbation_enabled      # bool
    @perturbation_type         # "dryden" | null
    @sigma_u, @sigma_v, @sigma_w  # if perturbation enabled
    /sensors
      /gps
        @enabled               # bool
        @accuracy_rms_m, @rate_hz
      /imu
        @enabled               # bool
        @accel_noise_density, @gyro_noise_density, @rate_hz

  /simulation
    @seed
    @sample_rate_hz            # null for auto
    @n_subswaths, @burst_length
    scene_center_m             # dataset (3,) float64 [optional]
    swath_range_m              # dataset (2,) float64 [optional]

  /processing
    @image_formation, @image_formation_params  # JSON
    @moco, @moco_params                        # JSON
    @autofocus, @autofocus_params              # JSON
    @geocoding, @geocoding_params              # JSON
    @polarimetric_decomposition, @polarimetric_decomposition_params  # JSON

/config                        # EXISTING — preserved for backwards compat
/raw_data                      # EXISTING — unchanged
/navigation                    # EXISTING — unchanged
/images                        # EXISTING — unchanged
```

## Compatibility Rules

1. **Reading v1 files**: If `/parameters` is absent, fall back to `/config` JSON strings. Import wizard reports missing parameters.
2. **Writing always v2**: All new saves include both `/parameters` (structured) and `/config` (JSON strings for legacy readers).
3. **Real measurement data**: May have `/raw_data` + `/navigation` but minimal or no `/parameters`. Import wizard detects gaps.
