# AutoDeal Mobile App (React Native)

## Overview
Mobile application for AutoDeal IA Hunter, providing on-the-go access to vehicle deals, valuations, and market intelligence.

## Tech Stack
- React Native (Expo)
- TypeScript
- React Navigation
- Axios (API client)
- React Query (data fetching)
- AsyncStorage (local storage)
- Push Notifications (Expo)

## Features

### Core Features
- **Vehicle Search**: Browse and filter vehicles by brand, model, price, year, etc.
- **Deal Alerts**: Push notifications for high-deal-score vehicles
- **Valuation**: Get instant vehicle valuations
- **Market Reports**: View market trends and analytics
- **Favorites**: Save interesting vehicles
- **Real-time Updates**: WebSocket integration for live vehicle updates

### Advanced Features
- **Camera Integration**: Take photos of vehicles for Vision AI analysis
- **Location-based**: GPS-based location filtering
- **Offline Mode**: Cache vehicle data for offline browsing
- **User Authentication**: Login/register with JWT tokens

## Project Structure

```
mobile/
├── App.tsx
├── assets/
├── components/
│   ├── VehicleCard.tsx
│   ├── DealBadge.tsx
│   ├── SearchBar.tsx
│   └── FilterModal.tsx
├── screens/
│   ├── HomeScreen.tsx
│   ├── VehicleListScreen.tsx
│   ├── VehicleDetailScreen.tsx
│   ├── ValuationScreen.tsx
│   ├── MarketReportScreen.tsx
│   ├── FavoritesScreen.tsx
│   ├── ProfileScreen.tsx
│   └── AuthScreen.tsx
├── navigation/
│   ├── AppNavigator.tsx
│   └── TabNavigator.tsx
├── services/
│   ├── api.ts
│   ├── auth.ts
│   └── websocket.ts
├── hooks/
│   ├── useVehicles.ts
│   ├── useDeals.ts
│   └── useAuth.ts
├── store/
│   ├── authSlice.ts
│   └── vehiclesSlice.ts
├── types/
│   ├── vehicle.ts
│   ├── deal.ts
│   └── user.ts
├── utils/
│   ├── formatters.ts
│   └── validators.ts
└── app.json
```

## API Integration

### Base URL
```
http://localhost:8000/api/v1
```

### Endpoints

#### Authentication
- `POST /auth/register` - Register new user
- `POST /auth/login` - Login and get token
- `GET /auth/me` - Get current user info

#### Vehicles
- `GET /vehicles` - List vehicles with filters
- `GET /vehicles/{id}` - Get vehicle details
- `POST /vehicles/valuate` - Valuate a vehicle

#### Deals
- `GET /deals` - Get top deals

#### Analytics
- `GET /analytics/market-report` - Get market report

#### WebSocket
- `WS /ws/vehicles` - Real-time vehicle updates

## Installation

```bash
cd mobile
npm install
```

## Running the App

### Development
```bash
npx expo start
```

### iOS
```bash
npx expo run-ios
```

### Android
```bash
npx expo run-android
```

## Configuration

### Environment Variables
Create `.env` file:
```
API_URL=http://localhost:8000/api/v1
WS_URL=ws://localhost:8000/api/v1/ws/vehicles
```

## Key Components

### VehicleCard
```typescript
interface VehicleCardProps {
  vehicle: Vehicle;
  onPress: () => void;
}
```

### ValuationScreen
- Input form for vehicle details
- Display valuation results
- Show deal score

### MarketReportScreen
- Display price trends chart
- Show supply/demand analysis
- Geographic distribution

## Push Notifications

### Setup
```typescript
import * as Notifications from 'expo-notifications';

Notifications.requestPermissionsAsync();
```

### Deal Alert Notification
```typescript
async function sendDealAlert(vehicle: Vehicle) {
  await Notifications.scheduleNotificationAsync({
    content: {
      title: 'New Deal Alert!',
      body: `${vehicle.brand} ${vehicle.model} - Deal Score: ${vehicle.deal_score}`,
      data: { vehicleId: vehicle.id },
    },
    trigger: null,
  });
}
```

## Camera Integration (Vision AI)

```typescript
import { Camera } from 'expo-camera';

async function takePhotoForAnalysis() {
  const { status } = await Camera.requestCameraPermissionsAsync();
  if (status === 'granted') {
    // Take photo and send to API for Vision AI analysis
  }
}
```

## Deployment

### Expo Build
```bash
eas build --platform android
eas build --platform ios
```

### Store Submission
- Google Play Store
- Apple App Store

## Future Enhancements
- [ ] AR vehicle visualization
- [ ] Voice search
- [ ] Social sharing
- [ ] Dark mode
- [ ] Multiple language support
- [ ] Payment integration for premium features

## Notes
- This is a placeholder structure for the mobile app
- Full implementation would require significant development effort
- Consider using Expo for easier development and deployment
- API integration requires the backend to be running
