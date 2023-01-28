#[macro_export]
macro_rules! resource_location {
    ($namespace:expr, $path:expr) => {
        formatcp!("{}:{}", $namespace, $path)
    };
}
