import { useEffect, useState } from "react";
import { View, StyleSheet, ActivityIndicator, Text, Alert } from "react-native";
import * as Location from "expo-location";
import Mapbox, { MapView, Camera, LocationPuck } from "@rnmapbox/maps";
import { MAPBOX_ACCESS_TOKEN } from "@/config/mapbox";

// Initialize Mapbox with access token
Mapbox.setAccessToken(MAPBOX_ACCESS_TOKEN);

interface UserCoordinates {
    latitude: number;
    longitude: number;
}

export default function MapScreen() {
    const [isLoading, setIsLoading] = useState(true);
    const [locationPermission, setLocationPermission] = useState<boolean | null>(null);
    const [userLocation, setUserLocation] = useState<UserCoordinates | null>(null);

    useEffect(() => {
        requestLocationPermission();
    }, []);

    const requestLocationPermission = async () => {
        try {
            const { status } = await Location.requestForegroundPermissionsAsync();
            const granted = status === "granted";
            setLocationPermission(granted);

            if (granted) {
                // Get initial location
                const location = await Location.getCurrentPositionAsync({
                    accuracy: Location.Accuracy.Balanced,
                });
                setUserLocation({
                    latitude: location.coords.latitude,
                    longitude: location.coords.longitude,
                });
            } else {
                Alert.alert(
                    "Location Permission Required",
                    "Trekkr needs location access to track your explorations and unlock areas on the map.",
                    [{ text: "OK" }]
                );
            }
        } catch (error) {
            console.error("Error requesting location permission:", error);
        } finally {
            setIsLoading(false);
        }
    };

    if (isLoading) {
        return (
            <View style={styles.centered}>
                <ActivityIndicator size="large" color="#10b981" />
                <Text style={styles.loadingText}>Loading map...</Text>
            </View>
        );
    }

    if (locationPermission === false) {
        return (
            <View style={styles.centered}>
                <Text style={styles.errorText}>Location permission denied</Text>
                <Text style={styles.subText}>
                    Enable location access in your device settings to use Trekkr
                </Text>
            </View>
        );
    }

    // Default to a world view if no user location
    const initialCoordinates = userLocation || { latitude: 20, longitude: 0 };
    const initialZoom = userLocation ? 12 : 2;

    return (
        <View style={styles.container}>
            <MapView
                style={styles.map}
                styleURL="mapbox://styles/mapbox/streets-v12"
                logoEnabled={false}
                attributionEnabled={true}
                attributionPosition={{ bottom: 8, right: 8 }}
                scaleBarEnabled={false}
            >
                <Camera
                    zoomLevel={initialZoom}
                    centerCoordinate={[initialCoordinates.longitude, initialCoordinates.latitude]}
                    animationMode="flyTo"
                    animationDuration={1000}
                />

                {locationPermission && (
                    <LocationPuck
                        puckBearing="heading"
                        puckBearingEnabled={true}
                        pulsing={{ isEnabled: true, color: "#10b981", radius: 50 }}
                    />
                )}
            </MapView>
        </View>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
    },
    map: {
        flex: 1,
    },
    centered: {
        flex: 1,
        justifyContent: "center",
        alignItems: "center",
        backgroundColor: "#f5f5f5",
        padding: 20,
    },
    loadingText: {
        marginTop: 12,
        fontSize: 16,
        color: "#666",
    },
    errorText: {
        fontSize: 18,
        fontWeight: "600",
        color: "#ef4444",
        textAlign: "center",
    },
    subText: {
        marginTop: 8,
        fontSize: 14,
        color: "#666",
        textAlign: "center",
    },
});
