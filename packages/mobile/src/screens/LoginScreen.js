import React, { useState, useEffect } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
} from "react-native";
import { colors, spacing, radius, layout } from "@agri/shared/theme";
import { useAuth } from "../context/AuthContext";
import { GoogleSignin } from "@react-native-google-signin/google-signin";
import Constants from "expo-constants";

export default function LoginScreen() {
  const { login, loginWithGoogle } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);

  useEffect(() => {
    // Configure Google Sign-In
    // The webClientId should be your Web client ID from Google Cloud Console
    // webClientId MUST be a Web OAuth client ID so the ID token audience
    // matches backend GOOGLE_CLIENT_ID (not the Android client ID).
    GoogleSignin.configure({
      webClientId: Constants.expoConfig?.extra?.googleWebClientId || "",
      offlineAccess: true,
    });
  }, []);

  const handleLogin = async () => {
    setLoading(true);
    setError(null);
    try {
      await login(email.trim(), password);
    } catch (e) {
      setError(e.message || "Login failed");
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleLogin = async () => {
    setGoogleLoading(true);
    setError(null);
    try {
      await GoogleSignin.hasPlayServices();
      const userInfo = await GoogleSignin.signIn();
      const idToken = userInfo.data?.idToken || userInfo.idToken;
      if (idToken) {
        await loginWithGoogle(idToken);
      } else {
        throw new Error("No ID token received from Google");
      }
    } catch (e) {
      setError(e.message || "Google Sign-In failed");
    } finally {
      setGoogleLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <View style={styles.card}>
        <Text style={styles.title}>AgriData Egypt</Text>
        <Text style={styles.subtitle}>Sign in to monitor your lands</Text>
        {error && <Text style={styles.error}>{error}</Text>}
        <TextInput
          style={styles.input}
          placeholder="Email"
          placeholderTextColor={colors.gray400}
          value={email}
          onChangeText={setEmail}
          autoCapitalize="none"
          keyboardType="email-address"
        />
        <TextInput
          style={styles.input}
          placeholder="Password"
          placeholderTextColor={colors.gray400}
          value={password}
          onChangeText={setPassword}
          secureTextEntry
        />
        <TouchableOpacity style={styles.button} onPress={handleLogin} disabled={loading || googleLoading}>
          {loading ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.buttonText}>Sign In</Text>
          )}
        </TouchableOpacity>

        <View style={styles.dividerContainer}>
          <View style={styles.divider} />
          <Text style={styles.dividerText}>OR</Text>
          <View style={styles.divider} />
        </View>

        <TouchableOpacity 
          style={[styles.button, styles.googleButton]} 
          onPress={handleGoogleLogin} 
          disabled={loading || googleLoading}
        >
          {googleLoading ? (
            <ActivityIndicator color={colors.green800} />
          ) : (
            <Text style={styles.googleButtonText}>Sign in with Google</Text>
          )}
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.green950,
    justifyContent: "center",
    padding: spacing.lg,
  },
  card: {
    backgroundColor: colors.bgPrimary,
    borderRadius: radius.xl,
    padding: spacing.xl,
  },
  title: {
    fontSize: 24,
    fontWeight: "700",
    color: colors.green800,
    marginBottom: spacing.xs,
  },
  subtitle: {
    fontSize: 15,
    color: colors.textSecondary,
    marginBottom: spacing.lg,
  },
  error: {
    color: colors.error,
    marginBottom: spacing.md,
    fontSize: 14,
  },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    padding: spacing.md,
    marginBottom: spacing.md,
    fontSize: 16,
    minHeight: layout.touchTarget,
  },
  button: {
    backgroundColor: colors.green600,
    borderRadius: radius.md,
    minHeight: layout.touchTarget,
    alignItems: "center",
    justifyContent: "center",
    marginTop: spacing.sm,
  },
  buttonText: {
    color: "#fff",
    fontWeight: "600",
    fontSize: 16,
  },
  dividerContainer: {
    flexDirection: "row",
    alignItems: "center",
    marginVertical: spacing.lg,
  },
  divider: {
    flex: 1,
    height: 1,
    backgroundColor: colors.border,
  },
  dividerText: {
    marginHorizontal: spacing.sm,
    color: colors.gray400,
    fontWeight: "600",
  },
  googleButton: {
    backgroundColor: "#fff",
    borderWidth: 1,
    borderColor: colors.border,
  },
  googleButtonText: {
    color: colors.gray800,
    fontWeight: "600",
    fontSize: 16,
  },
});