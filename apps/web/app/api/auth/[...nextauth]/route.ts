import NextAuth from "next-auth";
import GoogleProvider from "next-auth/providers/google";

const authOptions = {
  providers: [
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID || "",
      clientSecret: process.env.GOOGLE_CLIENT_SECRET || "",
    }),
  ],
  secret: process.env.NEXTAUTH_SECRET || "fallback_secret_for_local_dev",
  callbacks: {
    async signIn({ user }: { user: any }) {
      try {
        const response = await fetch(`${process.env.INTERNAL_API_URL || "http://127.0.0.1:8000"}/users/sync`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            email: user.email,
            full_name: user.name || "Google User",
          }),
        });
        if (response.ok) {
          const data = await response.json();
          user.id = data.id;
          user.org_id = data.org_id;
          return true;
        }
      } catch (error) {
        console.error("User sync failed:", error);
      }
      // If sync fails, allow login but with fallback demo values
      user.org_id = "11111111-1111-1111-1111-111111111111";
      user.id = "22222222-2222-2222-2222-222222222222";
      return true;
    },
    async jwt({ token, user }: { token: any; user?: any }) {
      if (user) {
        token.id = user.id;
        token.org_id = user.org_id;
      }
      return token;
    },
    async session({ session, token }: { session: any; token: any }) {
      if (session.user) {
        session.user.id = token.id;
        session.user.org_id = token.org_id;
      }
      return session;
    },
  },
};

const handler = NextAuth(authOptions);

export { handler as GET, handler as POST };
