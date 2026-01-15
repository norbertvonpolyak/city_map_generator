from generator.specs import spec_from_size_key

def main() -> None:
    spec = spec_from_size_key("50x70", extent_m=5000, dpi=300)

    print("size_cm:", (spec.width_cm, spec.height_cm))
    print("aspect_ratio:", spec.aspect_ratio)          # várható: (5, 7)
    print("fig_size_inches:", spec.fig_size_inches)    # kb: (19.685..., 27.559...)
    print("frame_half_sizes_m:", spec.frame_half_sizes_m)  # half_w ~ 3571.43, half_h = 5000

if __name__ == "__main__":
    main()
