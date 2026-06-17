from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Game, GameWinner
from .serializers import (
    GameConditionSerializer,
    GameCreateSerializer,
    GameSerializer,
    GameWinnerSerializer,
)


class GameListCreateView(generics.ListCreateAPIView):
    """
    List and create games with nested conditions and rules.
    """

    queryset = Game.objects.all().order_by("-created_at")
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return GameCreateSerializer
        return GameSerializer


class ActiveGameView(APIView):
    """
    Get the currently active game along with its active condition and details.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        active_game = Game.objects.filter(is_active=True).first()
        if not active_game:
            return Response(None, status=status.HTTP_200_OK)
        serializer = GameSerializer(active_game)
        return Response(serializer.data)


class ChooseRandomConditionView(APIView):
    """
    Trigger selecting a random condition for the active game.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        active_game = Game.objects.filter(is_active=True).first()
        if not active_game:
            return Response(
                {"error": "No active game found."}, status=status.HTTP_404_NOT_FOUND
            )

        selected_condition = active_game.choose_random_condition()
        if not selected_condition:
            return Response(
                {"error": "No active conditions found for this game."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = GameConditionSerializer(selected_condition)
        return Response(
            {
                "message": f"Successfully activated condition: {str(selected_condition)}",
                "condition": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class GameWinnerListView(generics.ListAPIView):
    """
    List all winners of the games.
    """

    queryset = GameWinner.objects.all().order_by("-won_at")
    serializer_class = GameWinnerSerializer
    permission_classes = [IsAuthenticated]


class GameDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete a game.
    Allows activating/deactivating a game by changing the 'is_active' field.
    """

    queryset = Game.objects.all()
    serializer_class = GameSerializer
    permission_classes = [IsAuthenticated]
